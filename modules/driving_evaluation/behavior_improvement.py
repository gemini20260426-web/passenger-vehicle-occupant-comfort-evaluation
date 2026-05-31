"""驾驶行为改进建议系统模块（负责分析驾驶弱点并生成改进建议）"""
import logging
import time
import datetime
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Union
from PySide6.QtCore import QObject, Signal, Slot, QMutex, QMutexLocker, QThread
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QLabel, QComboBox, QPushButton, QGroupBox, QFormLayout,
                             QTextEdit, QDialog, QDialogButtonBox, QTabWidget, QProgressDialog,
                             QTreeWidget, QTreeWidgetItem, QScrollArea, QFrame)
from PySide6.QtGui import QColor, Qt, QFont, QIcon

class BehaviorImprovementSystem(QObject):
    """驾驶行为改进建议系统（新增核心类）"""
    # 信号定义
    improvement_analysis_completed = Signal(str)  # 分析完成信号（司机ID）
    recommendations_updated = Signal(str)  # 建议更新信号（司机ID）
    error_occurred = Signal(str)  # 错误信号
    
    def __init__(self, core_services):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.core_services = core_services  # 核心服务引用
        
        # 线程安全锁
        self.analysis_lock = QMutex()
        
        # 分析结果缓存
        self.analysis_results: Dict[str, Dict[str, Any]] = {}
        
        # 分析任务队列
        self.analysis_queue: List[Tuple[str, str]] = []  # (司机ID, 时间范围: daily, weekly, monthly)
        self.analysis_in_progress: Dict[str, bool] = {}
        
        # 加载改进建议配置
        self._load_improvement_config()
        
        # 连接配置变更信号
        self.core_services.config_manager.config_changed.connect(self._on_config_changed)
        
        # 连接评分更新信号
        self.core_services.driver_scoring_system.scoring_completed.connect(self._on_scoring_completed)
        
        # 启动分析线程
        self._start_analysis_thread()

    def _load_improvement_config(self) -> None:
        """加载改进建议配置（新增）"""
        # 从配置管理器获取相关配置
        config = self.core_services.config_manager.get_config('behavior_improvement', {})
        
        # 弱点识别阈值
        self.weakness_thresholds = config.get('weakness_thresholds', {
            'score_threshold': 70,  # 低于此分数的项被视为弱点
            'alert_factor_threshold': 0.3,  # 告警中该因素占比阈值
            'trend_drop_threshold': 5  # 趋势下降阈值（分）
        })
        
        # 改进建议模板库
        self.recommendation_templates = config.get('recommendation_templates', {
            'safe_speed': {
                'low_score': [
                    "1. 注意观察道路限速标志，提前减速至规定速度。",
                    "2. 在学校区域、居民区和转弯处特别注意控制车速。",
                    "3. 使用车辆巡航控制功能保持稳定速度。",
                    "4. 提前预判路况变化，避免急加速后又急刹车。"
                ],
                'medium_score': [
                    "1. 高速公路上保持与前车的安全距离，避免因跟车过近而被迫急刹。",
                    "2. 雨天、雾天等恶劣天气应降低车速，比正常速度低20%。",
                    "3. 注意下坡路段控制车速，避免长时间刹车导致过热。"
                ]
            },
            'smooth_acceleration': {
                'low_score': [
                    "1. 起步时缓慢踩下油门，避免急加速。",
                    "2. 加速过程保持平稳，避免频繁变更加速度。",
                    "3. 预判交通信号灯变化，提前做好加速或减速准备。",
                    "4. 载重较大时更应注意平稳加速，减少对车辆的损耗。"
                ],
                'medium_score': [
                    "1. 高速公路并入主车道时，逐渐加速至与车流速度匹配。",
                    "2. 避免在弯道中加速，应在进入弯道前完成加速。",
                    "3. 注意发动机转速，避免高转速加速。"
                ]
            },
            'gentle_braking': {
                'low_score': [
                    "1. 提前观察路况，发现需要减速时提前轻踩刹车。",
                    "2. 避免频繁急刹车，保持与前车的安全距离。",
                    "3. 长下坡时使用发动机制动，减少刹车使用频率。",
                    "4. 雨天路滑时，刹车更应提前且轻柔，避免打滑。"
                ],
                'medium_score': [
                    "1. 接近停车线时，提前松油门滑行，最后轻踩刹车停车。",
                    "2. 转弯前提前减速，避免在转弯过程中刹车。",
                    "3. 注意刹车踏板反馈，避免一脚到底的刹车方式。"
                ]
            },
            'lane_discipline': {
                'low_score': [
                    "1. 行驶时保持在车道中央，避免频繁偏离。",
                    "2. 变道前提前打转向灯，确认安全后再平稳变道。",
                    "3. 避免连续变道，每次变道只变更一个车道。",
                    "4. 高速公路上，除非超车，否则保持在右侧车道行驶。"
                ],
                'medium_score': [
                    "1. 注意观察后视镜，了解周围车辆位置后再变道。",
                    "2. 避免在弯道、坡道或视线不良的地方变道。",
                    "3. 遇交通拥堵时，保持在本车道依次行驶，不随意穿插。"
                ]
            },
            'compliance': {
                'low_score': [
                    "1. 严格遵守交通信号灯，不闯红灯。",
                    "2. 注意礼让行人，特别是在人行横道处。",
                    "3. 禁止在禁止停车区域停车，包括消防通道。",
                    "4. 不占用应急车道，除非遇到紧急情况。",
                    "5. 定期学习最新交通法规，了解规则变化。"
                ],
                'medium_score': [
                    "1. 通过路口时减速观察，确认安全后再通过。",
                    "2. 注意限速变化，特别是在限速摄像头附近。",
                    "3. 夜间行车合理使用灯光，避免远光灯干扰对向车辆。"
                ]
            }
        })
        
        # 培训资源库
        self.training_resources = config.get('training_resources', {
            'safe_speed': [
                {"title": "安全车速控制技巧", "type": "video", "duration": "15分钟"},
                {"title": "不同路况下的速度选择", "type": "document", "pages": 8}
            ],
            'smooth_acceleration': [
                {"title": "平稳加速驾驶方法", "type": "video", "duration": "12分钟"},
                {"title": "经济性加速技巧", "type": "document", "pages": 6}
            ],
            'gentle_braking': [
                {"title": "预见性刹车技巧", "type": "video", "duration": "10分钟"},
                {"title": "刹车系统保养与正确使用", "type": "document", "pages": 5}
            ],
            'lane_discipline': [
                {"title": "车道保持与安全变道", "type": "video", "duration": "18分钟"},
                {"title": "高速公路车道使用规范", "type": "document", "pages": 7}
            ],
            'compliance': [
                {"title": "最新交通法规解读", "type": "video", "duration": "25分钟"},
                {"title": "常见交通违规及后果", "type": "document", "pages": 12}
            ]
        })
        
        # 分析参数
        self.analysis_parameters = config.get('analysis_parameters', {
            'min_data_points': 10,  # 最小数据点数量
            'trend_analysis_periods': 3,  # 趋势分析周期数
            'comparison_percentile': 0.3  # 与优秀司机比较的百分位（前30%为优秀）
        })

    def _start_analysis_thread(self) -> None:
        """启动分析线程（新增）"""
        self.analysis_thread = BehaviorAnalysisThread(self)
        self.analysis_thread.start()

    def analyze_driver_behavior(self, driver_id: str, time_range: str = 'weekly') -> Optional[Dict[str, Any]]:
        """分析司机驾驶行为并生成改进建议（新增核心方法）"""
        if not driver_id:
            self.logger.error("司机ID不能为空")
            return None
            
        # 检查是否正在分析
        with QMutexLocker(self.analysis_lock):
            if driver_id in self.analysis_in_progress and self.analysis_in_progress[driver_id]:
                self.logger.info(f"司机 {driver_id} 的驾驶行为分析正在进行中")
                return None
                
            # 标记为分析中
            self.analysis_in_progress[driver_id] = True
        
        try:
            self.logger.info(f"开始分析司机 {driver_id} 的{time_range}驾驶行为")
            
            # 获取司机信息
            driver_info = self.core_services.driver_manager.get_driver_info(driver_id)
            if not driver_info:
                self.logger.error(f"司机 {driver_id} 不存在")
                return None
                
            driver_name = driver_info.get('name', driver_id)
            
            # 获取司机评分数据
            score_data = self.core_services.driver_scoring_system.get_driver_score(driver_id, time_range)
            if not score_data:
                # 尝试计算评分
                score_data = self.core_services.driver_scoring_system.calculate_driver_score(driver_id, time_range)
                if not score_data:
                    self.logger.error(f"无法获取司机 {driver_id} 的评分数据，无法进行行为分析")
                    return None
            
            # 确定时间范围
            window_days = self.core_services.driver_scoring_system.scoring_parameters['history_window_days'].get(
                time_range, 7
            )
            
            end_time = time.time()
            start_time = end_time - (window_days * 86400)
            
            # 获取该时间段内的驾驶行为数据
            driving_data = self.core_services.storage_manager.get_driver_behavior_data(
                driver_id=driver_id,
                start_time=start_time,
                end_time=end_time
            )
            
            if not driving_data or len(driving_data) < self.analysis_parameters['min_data_points']:
                self.logger.warning(f"司机 {driver_id} 在指定时间范围内数据不足，无法进行有效分析")
                return None
            
            # 识别驾驶弱点
            weaknesses = self._identify_weaknesses(driver_id, score_data, driving_data)
            
            # 分析弱点原因
            weakness_causes = self._analyze_weakness_causes(driver_id, weaknesses, driving_data)
            
            # 生成改进建议
            recommendations = self._generate_recommendations(weaknesses, weakness_causes)
            
            # 获取相关培训资源
            training_resources = self._get_relevant_training_resources(weaknesses)
            
            # 分析改进潜力
            improvement_potential = self._analyze_improvement_potential(driver_id, score_data, weaknesses)
            
            # 构建分析结果
            result = {
                'driver_id': driver_id,
                'driver_name': driver_name,
                'time_range': time_range,
                'window_days': window_days,
                'start_time': start_time,
                'end_time': end_time,
                'start_time_str': datetime.datetime.fromtimestamp(start_time).strftime("%Y-%m-%d"),
                'end_time_str': datetime.datetime.fromtimestamp(end_time).strftime("%Y-%m-%d"),
                'overall_score': score_data['total_score'],
                'overall_grade': score_data['grade'],
                'weaknesses': weaknesses,
                'weakness_causes': weakness_causes,
                'recommendations': recommendations,
                'training_resources': training_resources,
                'improvement_potential': improvement_potential,
                'analysis_time': time.time(),
                'analysis_time_str': datetime.datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # 保存到缓存
            with QMutexLocker(self.analysis_lock):
                if driver_id not in self.analysis_results:
                    self.analysis_results[driver_id] = {}
                self.analysis_results[driver_id][time_range] = result
            
            self.logger.info(f"司机 {driver_id} 的驾驶行为分析完成，发现 {len(weaknesses)} 个需要改进的方面")
            
            # 发出完成信号
            self.improvement_analysis_completed.emit(driver_id)
            
            return result
            
        except Exception as e:
            error_msg = f"分析司机 {driver_id} 驾驶行为失败: {str(e)}"
            self.logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return None
        finally:
            # 标记为分析完成
            with QMutexLocker(self.analysis_lock):
                if driver_id in self.analysis_in_progress:
                    self.analysis_in_progress[driver_id] = False

    def _identify_weaknesses(self, driver_id: str, score_data: Dict[str, Any], driving_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """识别驾驶弱点（新增）"""
        weaknesses = []
        
        # 1. 基于评分识别弱点（低于阈值的项目）
        for item_key, item_score in score_data['items'].items():
            if item_score['score'] < self.weakness_thresholds['score_threshold']:
                # 获取项目信息
                item_info = self.core_services.driver_scoring_system.scoring_items.get(item_key, {})
                
                weakness = {
                    'category': item_key,
                    'category_name': item_info.get('name', item_key),
                    'score': item_score['score'],
                    'severity': 'high' if item_score['score'] < self.weakness_thresholds['score_threshold'] * 0.8 else 'medium',
                    'reason': f"评分较低（{item_score['score']}分），低于阈值（{self.weakness_thresholds['score_threshold']}分）",
                    'details': item_score['details'],
                    'alert_related': False
                }
                
                weaknesses.append(weakness)
        
        # 2. 基于风险告警识别弱点
        alerts = self.core_services.alert_manager.get_alert_history({
            'driver_id': driver_id,
            'start_time': score_data['start_time'],
            'end_time': score_data['end_time']
        })
        
        if alerts:
            # 统计各风险因素出现频率
            factor_counts = {}
            total_factors = 0
            
            for alert in alerts:
                for factor in alert.get('risk_factors', []):
                    factor_type = factor.get('type', 'unknown')
                    factor_counts[factor_type] = factor_counts.get(factor_type, 0) + 1
                    total_factors += 1
            
            # 识别在告警中占比高的因素
            if total_factors > 0:
                for factor_type, count in factor_counts.items():
                    factor_ratio = count / total_factors
                    
                    if factor_ratio >= self.weakness_thresholds['alert_factor_threshold']:
                        # 检查是否已在弱点列表中
                        existing = next((w for w in weaknesses if w['category'] == factor_type), None)
                        
                        if existing:
                            # 更新现有弱点
                            existing['alert_related'] = True
                            existing['reason'] += f"，且在风险告警中频繁出现（占比 {factor_ratio*100:.1f}%）"
                        else:
                            # 添加新弱点
                            item_info = self.core_services.driver_scoring_system.scoring_items.get(factor_type, {})
                            
                            # 查找该项目的评分
                            item_score = next((s for k, s in score_data['items'].items() if k == factor_type), None)
                            score = item_score['score'] if item_score else 0
                            
                            weaknesses.append({
                                'category': factor_type,
                                'category_name': item_info.get('name', factor_type),
                                'score': score,
                                'severity': 'high',
                                'reason': f"在风险告警中频繁出现（占比 {factor_ratio*100:.1f}%）",
                                'details': {'alert_count': count, 'alert_ratio': factor_ratio},
                                'alert_related': True
                            })
        
        # 3. 基于趋势识别弱点（评分下降的项目）
        trend_period = self.analysis_parameters['trend_analysis_periods']
        if trend_period > 1:
            # 获取历史评分数据
            prev_time_ranges = []
            current_period = score_data['window_days']
            
            for i in range(1, trend_period + 1):
                prev_end_time = score_data['start_time']
                prev_start_time = prev_end_time - (current_period * 86400)
                
                # 获取该时间段的评分
                prev_score = self.core_services.storage_manager.get_driver_score_history(
                    driver_id=driver_id,
                    start_time=prev_start_time,
                    end_time=prev_end_time
                )
                
                if prev_score:
                    prev_time_ranges.append({
                        'start_time': prev_start_time,
                        'end_time': prev_end_time,
                        'score_data': prev_score
                    })
            
            # 分析趋势
            if len(prev_time_ranges) >= 1:
                # 取最近一个周期的评分进行比较
                prev_score_data = prev_time_ranges[0]['score_data']
                
                for item_key, curr_item_score in score_data['items'].items():
                    # 查找历史项目评分
                    prev_item_score = next((s for k, s in prev_score_data['items'].items() if k == item_key), None)
                    
                    if prev_item_score:
                        score_change = curr_item_score['score'] - prev_item_score['score']
                        
                        # 如果分数下降超过阈值
                        if score_change < -self.weakness_thresholds['trend_drop_threshold']:
                            # 检查是否已在弱点列表中
                            existing = next((w for w in weaknesses if w['category'] == item_key), None)
                            
                            if existing:
                                # 更新现有弱点
                                existing['reason'] += f"，且近期评分下降明显（下降 {abs(score_change):.1f} 分）"
                            else:
                                # 添加新弱点
                                item_info = self.core_services.driver_scoring_system.scoring_items.get(item_key, {})
                                
                                weaknesses.append({
                                    'category': item_key,
                                    'category_name': item_info.get('name', item_key),
                                    'score': curr_item_score['score'],
                                    'severity': 'medium',
                                    'reason': f"近期评分下降明显（下降 {abs(score_change):.1f} 分）",
                                    'details': {
                                        'previous_score': prev_item_score['score'],
                                        'current_score': curr_item_score['score'],
                                        'score_change': score_change
                                    },
                                    'alert_related': False
                                })
        
        # 按严重程度和评分排序（严重的在前，评分低的在前）
        weaknesses.sort(key=lambda x: (0 if x['severity'] == 'high' else 1, x['score']))
        
        return weaknesses

    def _analyze_weakness_causes(self, driver_id: str, weaknesses: List[Dict[str, Any]], driving_data: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """分析弱点原因（新增）"""
        causes = {}
        
        # 转换为DataFrame便于分析
        df = pd.DataFrame(driving_data)
        
        for weakness in weaknesses:
            category = weakness['category']
            causes[category] = []
            
            # 分析各类型弱点的具体原因
            if category == 'safe_speed':
                # 安全车速弱点原因分析
                if 'speed' in df.columns and 'speed_limit' in df.columns:
                    # 超速情况分析
                    speeding = df[df['speed'] > df['speed_limit']]
                    
                    if len(speeding) > 0:
                        # 超速时段分析
                        speeding['hour'] = pd.to_datetime(speeding['timestamp'], unit='s').dt.hour
                        hour_counts = speeding['hour'].value_counts()
                        peak_hour = hour_counts.index[0] if not hour_counts.empty else -1
                        
                        if peak_hour != -1:
                            period = "上午" if 6 <= peak_hour < 12 else \
                                     "下午" if 12 <= peak_hour < 18 else \
                                     "晚上" if 18 <= peak_hour < 22 else "凌晨"
                            causes[category].append(f"在{period}（{peak_hour}点左右）超速行为较多")
                        
                        # 超速地点分析
                        if 'location' in df.columns and not df['location'].isna().all():
                            location_counts = speeding['location'].value_counts()
                            if not location_counts.empty:
                                top_location = location_counts.index[0]
                                causes[category].append(f"在{top_location}区域频繁超速")
            
            elif category == 'smooth_acceleration':
                # 平稳加速弱点原因分析
                if 'acceleration' in df.columns:
                    # 急加速情况分析
                    harsh_accel = df[abs(df['acceleration']) > 2.5]
                    
                    if len(harsh_accel) > 0:
                        # 急加速场景分析
                        if 'scenario' in df.columns:
                            scenario_counts = harsh_accel['scenario'].value_counts()
                            if not scenario_counts.empty:
                                top_scenario = scenario_counts.index[0]
                                scenario_map = {
                                    'start': '起步时',
                                    'overtake': '超车时',
                                    'traffic_light': '红绿灯起步时',
                                    'highway': '高速公路上',
                                    'urban': '城市道路上'
                                }
                                causes[category].append(f"{scenario_map.get(top_scenario, top_scenario)}急加速行为较多")
            
            elif category == 'gentle_braking':
                # 平稳刹车弱点原因分析
                if 'braking_force' in df.columns:
                    # 急刹车情况分析
                    harsh_braking = df[df['braking_force'] > 0.8]
                    
                    if len(harsh_braking) > 0:
                        # 急刹车场景分析
                        if 'distance_to_vehicle' in df.columns:
                            close_distance = harsh_braking[harsh_braking['distance_to_vehicle'] < 50]
                            if len(close_distance) > len(harsh_braking) * 0.6:
                                causes[category].append("与前车距离过近导致频繁急刹车")
                        
                        if 'scenario' in df.columns:
                            scenario_counts = harsh_braking['scenario'].value_counts()
                            if not scenario_counts.empty:
                                top_scenario = scenario_counts.index[0]
                                causes[category].append(f"{top_scenario}场景下急刹车行为较多")
            
            elif category == 'lane_discipline':
                # 车道规范弱点原因分析
                if 'lane_deviation' in df.columns:
                    # 车道偏离情况分析
                    deviations = df[df['lane_deviation'] > 0.5]
                    
                    if len(deviations) > 0:
                        # 车道偏离时段分析
                        if 'fatigue_level' in df.columns:
                            high_fatigue = deviations[df['fatigue_level'] > 0.7]
                            if len(high_fatigue) > len(deviations) * 0.4:
                                causes[category].append("疲劳驾驶可能导致频繁车道偏离")
                        
                        # 变道分析
                        if 'lane_changes' in df.columns:
                            total_changes = df['lane_changes'].sum()
                            driving_hours = (df['timestamp'].max() - df['timestamp'].min()) / 3600
                            
                            if driving_hours > 0:
                                changes_per_hour = total_changes / driving_hours
                                if changes_per_hour > 15:  # 每小时变道超过15次
                                    causes[category].append("变道过于频繁，增加了风险")
            
            elif category == 'compliance':
                # 交通规则遵守弱点原因分析
                if 'traffic_violations' in df.columns:
                    violations = []
                    for v_list in df['traffic_violations']:
                        if isinstance(v_list, list):
                            violations.extend(v_list)
                    
                    if violations:
                        # 违规类型分析
                        violation_types = [v.get('type', 'unknown') for v in violations]
                        type_counts = pd.Series(violation_types).value_counts()
                        
                        if not type_counts.empty:
                            top_violation = type_counts.index[0]
                            violation_map = {
                                'red_light': '闯红灯',
                                'no_stop': '未礼让行人',
                                'wrong_way': '逆行',
                                'parking': '违规停车',
                                'phone': '驾驶时使用手机'
                            }
                            causes[category].append(f"{violation_map.get(top_violation, top_violation)}行为频繁")
        
        return causes

    def _generate_recommendations(self, weaknesses: List[Dict[str, Any]], causes: Dict[str, List[str]]) -> Dict[str, List[Dict[str, Any]]]:
        """生成改进建议（新增）"""
        recommendations = {}
        
        for weakness in weaknesses:
            category = weakness['category']
            category_name = weakness['category_name']
            severity = weakness['severity']
            
            # 基础建议（基于模板）
            base_recommendations = []
            
            # 根据严重程度选择不同模板
            if severity == 'high':
                template_key = 'low_score'
            else:
                template_key = 'medium_score'
            
            # 获取模板建议
            if category in self.recommendation_templates and template_key in self.recommendation_templates[category]:
                for idx, rec_text in enumerate(self.recommendation_templates[category][template_key]):
                    base_recommendations.append({
                        'id': f"{category}_base_{idx}",
                        'text': rec_text,
                        'priority': 'high' if idx < 2 else 'medium',
                        'type': 'general'
                    })
            
            # 针对性建议（基于具体原因）
            targeted_recommendations = []
            
            if category in causes and causes[category]:
                for cause in causes[category]:
                    # 根据具体原因生成针对性建议
                    if category == 'safe_speed':
                        if '超速' in cause:
                            if '时段' in cause or '点左右' in cause:
                                targeted_recommendations.append({
                                    'id': f"{category}_target_{len(targeted_recommendations)}",
                                    'text': f"{cause}，建议在此时间段特别注意车速表，提前减速。",
                                    'priority': 'high',
                                    'type': 'targeted'
                                })
                            elif '区域' in cause:
                                targeted_recommendations.append({
                                    'id': f"{category}_target_{len(targeted_recommendations)}",
                                    'text': f"{cause}，建议熟悉该区域的限速规定，设置导航提醒。",
                                    'priority': 'high',
                                    'type': 'targeted'
                                })
                    
                    elif category == 'smooth_acceleration':
                        if '急加速' in cause:
                            targeted_recommendations.append({
                                'id': f"{category}_target_{len(targeted_recommendations)}",
                                'text': f"{cause}，建议提前预判，缓慢踩油门，保持平稳加速。",
                                'priority': 'high',
                                'type': 'targeted'
                            })
                    
                    elif category == 'gentle_braking':
                        if '急刹车' in cause:
                            if '距离过近' in cause:
                                targeted_recommendations.append({
                                    'id': f"{category}_target_{len(targeted_recommendations)}",
                                    'text': f"{cause}，建议保持与前车的安全距离（至少2秒车程），提前观察路况。",
                                    'priority': 'high',
                                    'type': 'targeted'
                                })
                            else:
                                targeted_recommendations.append({
                                    'id': f"{category}_target_{len(targeted_recommendations)}",
                                    'text': f"{cause}，建议提前松油门滑行，减少刹车使用频率。",
                                    'priority': 'high',
                                    'type': 'targeted'
                                })
                    
                    elif category == 'lane_discipline':
                        if '车道偏离' in cause:
                            if '疲劳' in cause:
                                targeted_recommendations.append({
                                    'id': f"{category}_target_{len(targeted_recommendations)}",
                                    'text': f"{cause}，建议驾驶2小时左右停车休息，避免疲劳驾驶。",
                                    'priority': 'high',
                                    'type': 'targeted'
                                })
                        elif '变道' in cause:
                            targeted_recommendations.append({
                                'id': f"{category}_target_{len(targeted_recommendations)}",
                                'text': f"{cause}，建议规划好路线，减少不必要的变道。",
                                'priority': 'medium',
                                'type': 'targeted'
                            })
                    
                    elif category == 'compliance':
                        if '违规' in cause:
                            targeted_recommendations.append({
                                'id': f"{category}_target_{len(targeted_recommendations)}",
                                'text': f"{cause}，建议加强相关交通法规学习，设置提醒。",
                                'priority': 'high',
                                'type': 'targeted'
                            })
            
            # 综合建议（基础建议 + 针对性建议）
            all_recommendations = targeted_recommendations + base_recommendations
            
            # 按优先级排序
            all_recommendations.sort(key=lambda x: 0 if x['priority'] == 'high' else 1)
            
            # 添加到结果
            recommendations[category] = {
                'category': category,
                'category_name': category_name,
                'severity': severity,
                'recommendations': all_recommendations
            }
        
        return recommendations

    def _get_relevant_training_resources(self, weaknesses: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """获取相关培训资源（新增）"""
        resources = {}
        
        for weakness in weaknesses:
            category = weakness['category']
            
            if category in self.training_resources:
                resources[category] = {
                    'category': category,
                    'category_name': weakness['category_name'],
                    'resources': self.training_resources[category]
                }
        
        return resources

    def _analyze_improvement_potential(self, driver_id: str, score_data: Dict[str, Any], weaknesses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析改进潜力（新增）"""
        # 获取优秀司机的平均评分作为参考
        top_drivers = self.core_services.driver_scoring_system.get_drivers_ranking(
            time_range=score_data['time_range'],
            top_n=int(self.analysis_parameters['comparison_percentile'] * 100)
        )
        
        # 计算优秀司机各项目的平均评分
        top_item_scores = {}
        if top_drivers and len(top_drivers) > 0:
            for item_key in score_data['items'].keys():
                scores = []
                for driver in top_drivers:
                    if item_key in driver['items']:
                        scores.append(driver['items'][item_key]['score'])
                
                if scores:
                    top_item_scores[item_key] = sum(scores) / len(scores)
        
        # 计算各弱点项目的改进潜力
        item_potentials = []
        total_potential_increase = 0.0
        
        for weakness in weaknesses:
            category = weakness['category']
            current_score = weakness['score']
            
            # 参考优秀司机的评分或满分100
            reference_score = top_item_scores.get(category, 100)
            
            # 计算可能的分数提升
            potential_increase = reference_score - current_score
            
            # 考虑权重的分数提升
            item_info = self.core_services.driver_scoring_system.scoring_items.get(category, {})
            weight = item_info.get('weight', 0)
            weighted_increase = potential_increase * weight
            
            total_potential_increase += weighted_increase
            
            item_potentials.append({
                'category': category,
                'category_name': weakness['category_name'],
                'current_score': current_score,
                'reference_score': reference_score,
                'potential_increase': potential_increase,
                'weighted_increase': weighted_increase,
                'weight': weight
            })
        
        # 计算总体可能提升到的分数
        potential_overall_score = min(100, score_data['total_score'] + total_potential_increase)
        potential_grade = self.core_services.driver_scoring_system._determine_grade(potential_overall_score)
        
        # 按提升潜力排序
        item_potentials.sort(key=lambda x: x['weighted_increase'], reverse=True)
        
        return {
            'current_overall_score': score_data['total_score'],
            'current_grade': score_data['grade'],
            'potential_overall_score': round(potential_overall_score, 1),
            'potential_grade': potential_grade,
            'potential_increase': round(total_potential_increase, 1),
            'item_potentials': item_potentials,
            'improvement_priority': [item['category'] for item in item_potentials[:3]]  # 前3名优先改进项
        }

    def get_improvement_analysis(self, driver_id: str, time_range: str = 'weekly') -> Optional[Dict[str, Any]]:
        """获取驾驶行为改进分析结果（新增）"""
        with QMutexLocker(self.analysis_lock):
            # 检查缓存中是否存在且未过期（2小时内）
            if driver_id in self.analysis_results and time_range in self.analysis_results[driver_id]:
                analysis_data = self.analysis_results[driver_id][time_range]
                if time.time() - analysis_data['analysis_time'] < 7200:  # 2小时
                    return analysis_data
        
        # 缓存不存在或已过期，触发分析
        self.queue_analysis_task(driver_id, time_range)
        return None

    def queue_analysis_task(self, driver_id: str, time_range: str = 'weekly') -> None:
        """排队分析任务（新增）"""
        with QMutexLocker(self.analysis_lock):
            # 检查是否已在队列中
            for task in self.analysis_queue:
                if task[0] == driver_id and task[1] == time_range:
                    return  # 已在队列中，无需重复添加
            
            # 添加到队列
            self.analysis_queue.append((driver_id, time_range))
            self.logger.info(f"司机 {driver_id} 的{time_range}驾驶行为分析任务已加入队列")

    def analyze_all_drivers_behavior(self, time_range: str = 'weekly') -> None:
        """分析所有司机的驾驶行为（新增）"""
        # 获取所有司机ID
        drivers = self.core_services.driver_manager.get_all_drivers()
        driver_ids = [d['id'] for d in drivers]
        
        # 添加到分析队列
        with QMutexLocker(self.analysis_lock):
            for driver_id in driver_ids:
                # 检查是否已在队列中
                exists = False
                for task in self.analysis_queue:
                    if task[0] == driver_id and task[1] == time_range:
                        exists = True
                        break
                
                if not exists:
                    self.analysis_queue.append((driver_id, time_range))
        
        self.logger.info(f"已将 {len(driver_ids)} 名司机的{time_range}驾驶行为分析任务加入队列")

    def get_weakness_distribution(self, time_range: str = 'weekly') -> Dict[str, int]:
        """获取弱点分布统计（新增）"""
        distribution = {
            'safe_speed': 0,
            'smooth_acceleration': 0,
            'gentle_braking': 0,
            'lane_discipline': 0,
            'compliance': 0
        }
        
        with QMutexLocker(self.analysis_lock):
            for driver_id, time_analyses in self.analysis_results.items():
                if time_range in time_analyses:
                    # 检查分析是否过期
                    if time.time() - time_analyses[time_range]['analysis_time'] < 7200:
                        for weakness in time_analyses[time_range]['weaknesses']:
                            if weakness['category'] in distribution:
                                distribution[weakness['category']] += 1
        
        return distribution

    @Slot(str, Any, Any)
    def _on_config_changed(self, path: str, old_value: Any, new_value: Any) -> None:
        """处理配置变更（新增）"""
        if path.startswith('behavior_improvement.'):
            self.logger.info(f"驾驶行为改进配置变更: {path}")
            self._load_improvement_config()

    @Slot(str)
    def _on_scoring_completed(self, driver_id: str) -> None:
        """评分计算完成后触发分析（新增）"""
        # 对刚完成评分的司机进行行为分析
        self.queue_analysis_task(driver_id, 'weekly')  # 默认分析周数据


class BehaviorAnalysisThread(QThread):
    """驾驶行为分析线程（新增）"""
    def __init__(self, improvement_system: BehaviorImprovementSystem):
        super().__init__()
        self.improvement_system = improvement_system
        self.logger = logging.getLogger(__name__)
        self.running = True
        self.check_interval = 60  # 检查间隔，秒

    def run(self) -> None:
        """运行分析线程"""
        self.logger.info("驾驶行为分析线程已启动")
        
        try:
            while self.running:
                # 检查任务队列
                task = None
                with QMutexLocker(self.improvement_system.analysis_lock):
                    if self.improvement_system.analysis_queue:
                        task = self.improvement_system.analysis_queue.pop(0)
                
                if task:
                    driver_id, time_range = task
                    self.logger.info(f"处理分析任务: 司机 {driver_id}, 时间范围 {time_range}")
                    
                    # 执行分析
                    self.improvement_system.analyze_driver_behavior(driver_id, time_range)
                else:
                    # 没有任务，休眠
                    for _ in range(self.check_interval):
                        if not self.running:
                            break
                        time.sleep(1)
                
                # 定期触发所有司机的行为分析（每周一次）
                current_hour = datetime.datetime.now().hour
                if current_hour == 2 and datetime.datetime.now().minute < 5:  # 凌晨2点左右
                    # 每周一进行一次全量分析
                    if datetime.datetime.now().weekday() == 0:  # 0表示周一
                        self.logger.info("触发每周驾驶行为全量分析")
                        self.improvement_system.analyze_all_drivers_behavior('weekly')
                    
                    # 避免重复触发，休眠10分钟
                    time.sleep(600)
                
        except Exception as e:
            self.logger.error(f"驾驶行为分析线程错误: {str(e)}")
        finally:
            self.logger.info("驾驶行为分析线程已停止")

    def stop(self) -> None:
        """停止分析线程"""
        self.running = False
        self.wait()


class DriverImprovementWidget(QWidget):
    """司机驾驶行为改进建议界面组件（新增）"""
    def __init__(self, improvement_system: BehaviorImprovementSystem, core_services, parent=None):
        super().__init__(parent)
        self.improvement_system = improvement_system
        self.core_services = core_services
        self.logger = logging.getLogger(__name__)
        
        # 当前选择的司机ID和时间范围
        self.current_driver_id = None
        self.current_time_range = 'weekly'
        
        # 初始化UI
        self._init_ui()
        
        # 连接信号
        self._connect_signals()

    def _init_ui(self) -> None:
        """初始化UI组件（新增）"""
        self.setWindowTitle("驾驶行为改进建议")
        self.resize(1000, 700)
        
        main_layout = QVBoxLayout(self)
        
        # 司机选择区域
        driver_layout = QHBoxLayout()
        
        # 司机选择下拉框
        self.driver_combo = QComboBox()
        self.driver_combo.setMinimumWidth(200)
        self._load_drivers_to_combo()
        
        # 时间范围选择
        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems(['daily', 'weekly', 'monthly', 'overall'])
        self.time_range_combo.setCurrentText('weekly')
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新分析")
        
        # 分析按钮
        self.analyze_btn = QPushButton("重新分析")
        
        driver_layout.addWidget(QLabel("选择司机:"))
        driver_layout.addWidget(self.driver_combo)
        driver_layout.addSpacing(10)
        driver_layout.addWidget(QLabel("时间范围:"))
        driver_layout.addWidget(self.time_range_combo)
        driver_layout.addSpacing(10)
        driver_layout.addWidget(self.refresh_btn)
        driver_layout.addWidget(self.analyze_btn)
        driver_layout.addStretch()
        
        main_layout.addLayout(driver_layout)
        
        # 分析结果标签页
        self.tab_widget = QTabWidget()
        
        # 概览标签页
        self.overview_tab = QWidget()
        self._init_overview_tab()
        self.tab_widget.addTab(self.overview_tab, "改进概览")
        
        # 弱点分析标签页
        self.weaknesses_tab = QWidget()
        self._init_weaknesses_tab()
        self.tab_widget.addTab(self.weaknesses_tab, "弱点分析")
        
        # 改进建议标签页
        self.recommendations_tab = QWidget()
        self._init_recommendations_tab()
        self.tab_widget.addTab(self.recommendations_tab, "改进建议")
        
        # 培训资源标签页
        self.training_tab = QWidget()
        self._init_training_tab()
        self.tab_widget.addTab(self.training_tab, "培训资源")
        
        main_layout.addWidget(self.tab_widget)

    def _init_overview_tab(self) -> None:
        """初始化概览标签页（新增）"""
        layout = QVBoxLayout(self.overview_tab)
        
        # 司机基本信息和评分
        info_layout = QHBoxLayout()
        
        # 左侧：基本信息
        self.basic_info_group = QGroupBox("司机基本信息")
        self.basic_form = QFormLayout()
        
        self.driver_name_label = QLabel("")
        self.driver_id_label = QLabel("")
        self.employment_date_label = QLabel("")
        self.vehicle_label = QLabel("")
        self.analysis_period_label = QLabel("")
        
        self.basic_form.addRow("司机ID:", self.driver_id_label)
        self.basic_form.addRow("司机姓名:", self.driver_name_label)
        self.basic_form.addRow("入职日期:", self.employment_date_label)
        self.basic_form.addRow("所属车辆:", self.vehicle_label)
        self.basic_form.addRow("分析周期:", self.analysis_period_label)
        
        self.basic_info_group.setLayout(self.basic_form)
        info_layout.addWidget(self.basic_info_group, 1)
        
        # 右侧：评分和改进潜力
        self.potential_group = QGroupBox("改进潜力")
        self.potential_layout = QVBoxLayout()
        
        # 评分对比
        self.score_comparison_layout = QHBoxLayout()
        
        self.current_score_label = QLabel("当前评分: --")
        self.current_score_label.setStyleSheet("font-size: 18px;")
        
        self.potential_score_label = QLabel("潜力评分: --")
        self.potential_score_label.setStyleSheet("font-size: 18px; color: #4caf50;")
        
        self.score_arrow_label = QLabel("→")
        self.score_arrow_label.setStyleSheet("font-size: 24px; padding: 0 10px;")
        
        self.score_comparison_layout.addWidget(self.current_score_label)
        self.score_comparison_layout.addWidget(self.score_arrow_label)
        self.score_comparison_layout.addWidget(self.potential_score_label)
        
        # 等级对比
        self.grade_comparison_layout = QHBoxLayout()
        
        self.current_grade_label = QLabel("当前等级: --")
        self.current_grade_label.setStyleSheet("font-size: 18px;")
        
        self.potential_grade_label = QLabel("潜力等级: --")
        self.potential_grade_label.setStyleSheet("font-size: 18px; color: #4caf50;")
        
        self.grade_arrow_label = QLabel("→")
        self.grade_arrow_label.setStyleSheet("font-size: 24px; padding: 0 10px;")
        
        self.grade_comparison_layout.addWidget(self.current_grade_label)
        self.grade_comparison_layout.addWidget(self.grade_arrow_label)
        self.grade_comparison_layout.addWidget(self.potential_grade_label)
        
        # 提升空间
        self.improvement_label = QLabel("提升空间: -- 分")
        self.improvement_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        # 优先改进项
        self.priority_label = QLabel("<strong>优先改进项:</strong>")
        self.priority_list_label = QLabel("")
        self.priority_list_label.setWordWrap(True)
        
        self.potential_layout.addLayout(self.score_comparison_layout)
        self.potential_layout.addLayout(self.grade_comparison_layout)
        self.potential_layout.addSpacing(10)
        self.potential_layout.addWidget(self.improvement_label)
        self.potential_layout.addSpacing(10)
        self.potential_layout.addWidget(self.priority_label)
        self.potential_layout.addWidget(self.priority_list_label)
        self.potential_layout.addStretch()
        
        self.potential_group.setLayout(self.potential_layout)
        info_layout.addWidget(self.potential_group, 1)
        
        layout.addLayout(info_layout)
        
        # 弱点概览
        self.weaknesses_overview_group = QGroupBox("驾驶弱点概览")
        self.weaknesses_overview_layout = QVBoxLayout()
        
        self.weaknesses_tree = QTreeWidget()
        self.weaknesses_tree.setHeaderLabel("驾驶弱点")
        self.weaknesses_tree.setAlternatingRowColors(True)
        
        self.weaknesses_overview_layout.addWidget(self.weaknesses_tree)
        
        self.weaknesses_overview_group.setLayout(self.weaknesses_overview_layout)
        layout.addWidget(self.weaknesses_overview_group)
        
        # 综合评价
        self.evaluation_group = QGroupBox("综合评价与改进方向")
        self.evaluation_layout = QVBoxLayout()
        
        self.evaluation_text = QTextEdit()
        self.evaluation_text.setReadOnly(True)
        self.evaluation_text.setMinimumHeight(100)
        
        self.evaluation_layout.addWidget(self.evaluation_text)
        self.evaluation_group.setLayout(self.evaluation_layout)
        
        layout.addWidget(self.evaluation_group)

    def _init_weaknesses_tab(self) -> None:
        """初始化弱点分析标签页（新增）"""
        layout = QVBoxLayout(self.weaknesses_tab)
        
        # 使用滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # 弱点内容将动态添加
        self.weaknesses_content_layout = content_layout
        
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

    def _init_recommendations_tab(self) -> None:
        """初始化改进建议标签页（新增）"""
        layout = QVBoxLayout(self.recommendations_tab)
        
        # 使用滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # 建议内容将动态添加
        self.recommendations_content_layout = content_layout
        
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

    def _init_training_tab(self) -> None:
        """初始化培训资源标签页（新增）"""
        layout = QVBoxLayout(self.training_tab)
        
        # 使用滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # 培训资源内容将动态添加
        self.training_content_layout = content_layout
        
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

    def _load_drivers_to_combo(self) -> None:
        """加载司机到下拉框（新增）"""
        # 保存当前选择
        current_text = self.driver_combo.currentText()
        
        # 清空下拉框
        self.driver_combo.clear()
        
        # 获取所有司机
        drivers = self.core_services.driver_manager.get_all_drivers()
        
        # 添加到下拉框
        for driver in drivers:
            self.driver_combo.addItem(f"{driver.get('name', '')} ({driver['id']})", driver['id'])
        
        # 恢复选择
        if current_text:
            index = self.driver_combo.findText(current_text)
            if index >= 0:
                self.driver_combo.setCurrentIndex(index)
            else:
                self.driver_combo.setCurrentIndex(0)

    def _connect_signals(self) -> None:
        """连接信号与槽（新增）"""
        # 分析完成信号
        self.improvement_system.improvement_analysis_completed.connect(self._on_analysis_completed)
        
        # 按钮信号
        self.refresh_btn.clicked.connect(self._load_analysis_data)
        self.analyze_btn.clicked.connect(self._analyze_current_driver)
        self.driver_combo.currentIndexChanged.connect(self._on_driver_changed)
        self.time_range_combo.currentTextChanged.connect(self._on_time_range_changed)

    def _on_driver_changed(self, index: int) -> None:
        """司机选择变更（新增）"""
        if index >= 0 and self.driver_combo.count() > 0:
            self.current_driver_id = self.driver_combo.itemData(index)
            self._load_analysis_data()

    def _on_time_range_changed(self, time_range: str) -> None:
        """时间范围变更（新增）"""
        self.current_time_range = time_range
        self._load_analysis_data()

    def _load_analysis_data(self) -> None:
        """加载分析数据（新增）"""
        if not self.current_driver_id:
            return
            
        # 获取分析结果
        analysis_data = self.improvement_system.get_improvement_analysis(
            self.current_driver_id, 
            self.current_time_range
        )
        
        if not analysis_data:
            # 没有分析数据，显示提示
            self._show_no_analysis_data_message()
            return
        
        # 更新概览标签页
        self._update_overview_tab(analysis_data)
        
        # 更新弱点分析标签页
        self._update_weaknesses_tab(analysis_data)
        
        # 更新改进建议标签页
        self._update_recommendations_tab(analysis_data)
        
        # 更新培训资源标签页
        self._update_training_tab(analysis_data)

    def _show_no_analysis_data_message(self) -> None:
        """显示无分析数据消息（新增）"""
        # 清空所有标签页内容
        self.driver_id_label.setText("")
        self.driver_name_label.setText("")
        self.employment_date_label.setText("")
        self.vehicle_label.setText("")
        self.analysis_period_label.setText("")
        
        self.current_score_label.setText("当前评分: --")
        self.potential_score_label.setText("潜力评分: --")
        self.improvement_label.setText("提升空间: -- 分")
        self.current_grade_label.setText("当前等级: --")
        self.potential_grade_label.setText("潜力等级: --")
        self.priority_list_label.setText("")
        
        self.weaknesses_tree.clear()
        self.evaluation_text.clear()
        
        # 清空其他标签页
        while self.weaknesses_content_layout.count():
            item = self.weaknesses_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        while self.recommendations_content_layout.count():
            item = self.recommendations_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        while self.training_content_layout.count():
            item = self.training_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 显示提示信息
        self.evaluation_text.setText("暂无驾驶行为分析数据，请点击\"重新分析\"按钮生成分析报告。")

    def _update_overview_tab(self, analysis_data: Dict[str, Any]) -> None:
        """更新概览标签页（新增）"""
        # 获取司机信息
        driver_info = self.core_services.driver_manager.get_driver_info(analysis_data['driver_id'])
        
        # 更新基本信息
        self.driver_id_label.setText(analysis_data['driver_id'])
        self.driver_name_label.setText(analysis_data['driver_name'])
        
        if driver_info:
            employment_date = driver_info.get('employment_date')
            if employment_date:
                self.employment_date_label.setText(
                    datetime.datetime.fromtimestamp(employment_date).strftime("%Y-%m-%d")
                )
            self.vehicle_label.setText(driver_info.get('vehicle_id', '未分配'))
        
        # 更新分析周期
        self.analysis_period_label.setText(
            f"{analysis_data['start_time_str']} 至 {analysis_data['end_time_str']}"
        )
        
        # 更新评分信息
        self.current_score_label.setText(f"当前评分: {analysis_data['overall_score']}")
        self.potential_score_label.setText(f"潜力评分: {analysis_data['improvement_potential']['potential_overall_score']}")
        self.improvement_label.setText(f"提升空间: {analysis_data['improvement_potential']['potential_increase']} 分")
        
        # 更新等级信息
        self.current_grade_label.setText(f"当前等级: {analysis_data['overall_grade']}")
        self.potential_grade_label.setText(f"潜力等级: {analysis_data['improvement_potential']['potential_grade']}")
        
        # 设置等级颜色
        grade_colors = {
            'S': "#d32f2f",
            'A': "#ff9800",
            'B': "#ffeb3b",
            'C': "#4caf50",
            'D': "#9e9e9e"
        }
        if analysis_data['overall_grade'] in grade_colors:
            self.current_grade_label.setStyleSheet(
                f"font-size: 18px; color: {grade_colors[analysis_data['overall_grade']]};"
            )
        
        if analysis_data['improvement_potential']['potential_grade'] in grade_colors:
            self.potential_grade_label.setStyleSheet(
                f"font-size: 18px; color: {grade_colors[analysis_data['improvement_potential']['potential_grade']]};"
            )
        
        # 更新优先改进项
        priority_items = []
        scoring_items = self.core_services.driver_scoring_system.scoring_items
        
        for category in analysis_data['improvement_potential']['improvement_priority']:
            item_info = scoring_items.get(category, {})
            priority_items.append(f"{item_info.get('name', category)}")
        
        self.priority_list_label.setText(", ".join(priority_items))
        
        # 更新弱点树
        self.weaknesses_tree.clear()
        
        for weakness in analysis_data['weaknesses']:
            # 创建弱点项
            weakness_item = QTreeWidgetItem([
                f"{weakness['category_name']} (评分: {weakness['score']})"
            ])
            
            # 设置颜色（严重程度）
            if weakness['severity'] == 'high':
                weakness_item.setForeground(0, QColor("#f44336"))
            else:
                weakness_item.setForeground(0, QColor("#ff9800"))
            
            # 添加原因
            reason_item = QTreeWidgetItem([f"原因: {weakness['reason']}"])
            weakness_item.addChild(reason_item)
            
            # 添加详细信息
            details_item = QTreeWidgetItem(["详细信息:"])
            weakness_item.addChild(details_item)
            
            for key, value in weakness['details'].items():
                key_name = key.replace('_', ' ').capitalize()
                details_item.addChild(QTreeWidgetItem([f"{key_name}: {value}"]))
            
            self.weaknesses_tree.addTopLevelItem(weakness_item)
            weakness_item.setExpanded(True)
        
        # 更新综合评价
        self._update_evaluation_text(analysis_data)

    def _update_evaluation_text(self, analysis_data: Dict[str, Any]) -> None:
        """更新综合评价文本（新增）"""
        # 构建综合评价
        evaluation = f"司机 {analysis_data['driver_name']} 的驾驶行为综合评分为 {analysis_data['overall_score']} 分，等级为 {analysis_data['overall_grade']}。\n\n"
        
        # 弱点总结
        if analysis_data['weaknesses']:
            evaluation += f"主要驾驶弱点有 {len(analysis_data['weaknesses'])} 项，分别是：\n"
            for weakness in analysis_data['weaknesses'][:3]:  # 只显示前3项
                evaluation += f"- {weakness['category_name']}: {weakness['reason']}\n"
            
            if len(analysis_data['weaknesses']) > 3:
                evaluation += f"- 以及其他 {len(analysis_data['weaknesses']) - 3} 项需要改进的方面\n"
        else:
            evaluation += "未发现明显驾驶弱点，驾驶行为表现良好。\n"
        
        # 改进潜力
        evaluation += f"\n通过针对性改进，预计可以将评分提升 {analysis_data['improvement_potential']['potential_increase']} 分，"
        evaluation += f"达到 {analysis_data['improvement_potential']['potential_overall_score']} 分，等级提升至 {analysis_data['improvement_potential']['potential_grade']}。\n"
        
        # 改进建议
        evaluation += "\n建议优先改进以下方面：\n"
        scoring_items = self.core_services.driver_scoring_system.scoring_items
        
        for i, category in enumerate(analysis_data['improvement_potential']['improvement_priority'][:3]):
            item_info = scoring_items.get(category, {})
            evaluation += f"{i+1}. {item_info.get('name', category)}: 预计可提升 {next((item['weighted_increase'] for item in analysis_data['improvement_potential']['item_potentials'] if item['category'] == category), 0)} 分\n"
        
        self.evaluation_text.setText(evaluation)

    def _update_weaknesses_tab(self, analysis_data: Dict[str, Any]) -> None:
        """更新弱点分析标签页（新增）"""
        # 清空现有内容
        while self.weaknesses_content_layout.count():
            item = self.weaknesses_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not analysis_data['weaknesses']:
            # 没有弱点
            no_weakness_label = QLabel("未发现明显驾驶弱点，驾驶行为表现良好。")
            no_weakness_label.setAlignment(Qt.AlignCenter)
            no_weakness_label.setStyleSheet("font-size: 16px; margin: 20px;")
            self.weaknesses_content_layout.addWidget(no_weakness_label)
            return
        
        # 添加每个弱点的详细分析
        for weakness in analysis_data['weaknesses']:
            # 创建弱点分组
            weakness_group = QGroupBox(weakness['category_name'])
            
            # 设置分组样式
            if weakness['severity'] == 'high':
                weakness_group.setStyleSheet("QGroupBox { color: #f44336; font-weight: bold; }")
            else:
                weakness_group.setStyleSheet("QGroupBox { color: #ff9800; font-weight: bold; }")
            
            weakness_layout = QVBoxLayout()
            
            # 基本信息
            info_layout = QFormLayout()
            
            info_layout.addRow("当前评分:", QLabel(f"{weakness['score']}"))
            info_layout.addRow("严重程度:", QLabel("高" if weakness['severity'] == 'high' else "中"))
            info_layout.addRow("问题原因:", QLabel(weakness['reason']))
            
            weakness_layout.addLayout(info_layout)
            
            # 分割线
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            weakness_layout.addWidget(line)
            
            # 详细信息
            weakness_layout.addWidget(QLabel("<strong>详细信息:</strong>"))
            
            details_text = QTextEdit()
            details_text.setReadOnly(True)
            details_text.setMinimumHeight(100)
            
            details_content = ""
            for key, value in weakness['details'].items():
                key_name = key.replace('_', ' ').capitalize()
                details_content += f"- {key_name}: {value}\n"
            
            details_text.setText(details_content)
            weakness_layout.addWidget(details_text)
            
            # 原因分析（如果有）
            if weakness['category'] in analysis_data['weakness_causes'] and analysis_data['weakness_causes'][weakness['category']]:
                weakness_layout.addWidget(QLabel("<strong>具体原因分析:</strong>"))
                
                causes_text = QTextEdit()
                causes_text.setReadOnly(True)
                causes_text.setMinimumHeight(80)
                
                causes_content = ""
                for i, cause in enumerate(analysis_data['weakness_causes'][weakness['category']]):
                    causes_content += f"{i+1}. {cause}\n"
                
                causes_text.setText(causes_content)
                weakness_layout.addWidget(causes_text)
            
            weakness_group.setLayout(weakness_layout)
            self.weaknesses_content_layout.addWidget(weakness_group)
        
        self.weaknesses_content_layout.addStretch()

    def _update_recommendations_tab(self, analysis_data: Dict[str, Any]) -> None:
        """更新改进建议标签页（新增）"""
        # 清空现有内容
        while self.recommendations_content_layout.count():
            item = self.recommendations_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not analysis_data['weaknesses']:
            # 没有弱点，显示通用建议
            general_group = QGroupBox("通用驾驶建议")
            general_layout = QVBoxLayout()
            
            general_text = QTextEdit()
            general_text.setReadOnly(True)
            general_text.setMinimumHeight(300)
            
            general_content = (
                "1. 保持定期车辆检查，确保车辆处于良好状态。\n"
                "2. 遵守交通规则，不超速、不酒驾、不疲劳驾驶。\n"
                "3. 保持良好驾驶习惯，平稳加速和刹车。\n"
                "4. 注意天气变化，恶劣天气适当降低车速。\n"
                "5. 定期参加安全驾驶培训，不断提升驾驶技能。"
            )
            
            general_text.setText(general_content)
            general_layout.addWidget(general_text)
            
            general_group.setLayout(general_layout)
            self.recommendations_content_layout.addWidget(general_group)
            return
        
        # 添加每个弱点的改进建议
        for weakness in analysis_data['weaknesses']:
            category = weakness['category']
            
            if category not in analysis_data['recommendations']:
                continue
                
            recommendations = analysis_data['recommendations'][category]
            
            # 创建建议分组
            rec_group = QGroupBox(f"{recommendations['category_name']} - 改进建议")
            rec_layout = QVBoxLayout()
            
            # 建议列表
            rec_list = QTreeWidget()
            rec_list.setHeaderLabels(["建议", "优先级"])
            rec_list.setAlternatingRowColors(True)
            rec_list.header().setSectionResizeMode(0, QHeaderView.Stretch)
            rec_list.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            
            for rec in recommendations['recommendations']:
                item = QTreeWidgetItem([rec['text'], rec['priority']])
                
                # 设置优先级颜色
                if rec['priority'] == 'high':
                    item.setForeground(1, QColor("#f44336"))
                else:
                    item.setForeground(1, QColor("#ff9800"))
                
                # 标记针对性建议
                if rec['type'] == 'targeted':
                    font = item.font(0)
                    font.setBold(True)
                    item.setFont(0, font)
                
                rec_list.addTopLevelItem(item)
            
            rec_layout.addWidget(rec_list)
            
            rec_group.setLayout(rec_layout)
            self.recommendations_content_layout.addWidget(rec_group)
        
        self.recommendations_content_layout.addStretch()

    def _update_training_tab(self, analysis_data: Dict[str, Any]) -> None:
        """更新培训资源标签页（新增）"""
        # 清空现有内容
        while self.training_content_layout.count():
            item = self.training_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 检查是否有相关培训资源
        has_resources = False
        
        # 添加每个弱点的培训资源
        for weakness in analysis_data['weaknesses']:
            category = weakness['category']
            
            if category not in analysis_data['training_resources']:
                continue
                
            resources = analysis_data['training_resources'][category]
            has_resources = True
            
            # 创建资源分组
            resource_group = QGroupBox(f"{resources['category_name']} - 培训资源")
            resource_layout = QVBoxLayout()
            
            # 资源列表
            resource_list = QTreeWidget()
            resource_list.setHeaderLabels(["标题", "类型", "信息"])
            resource_list.setAlternatingRowColors(True)
            resource_list.header().setSectionResizeMode(0, QHeaderView.Stretch)
            resource_list.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            resource_list.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
            
            for res in resources['resources']:
                info = f"{res['duration']}" if res['type'] == 'video' else f"{res['pages']}页"
                item = QTreeWidgetItem([res['title'], res['type'], info])
                resource_list.addTopLevelItem(item)
            
            # 添加学习按钮
            learn_btn = QPushButton(f"查看{resources['category_name']}相关培训")
            learn_btn.setStyleSheet("background-color: #e3f2fd;")
            
            resource_layout.addWidget(resource_list)
            resource_layout.addWidget(learn_btn)
            
            resource_group.setLayout(resource_layout)
            self.training_content_layout.addWidget(resource_group)
        
        if not has_resources:
            # 没有相关培训资源
            no_resource_label = QLabel("暂无相关培训资源")
            no_resource_label.setAlignment(Qt.AlignCenter)
            no_resource_label.setStyleSheet("font-size: 16px; margin: 20px;")
            self.training_content_layout.addWidget(no_resource_label)
        else:
            self.training_content_layout.addStretch()

    @Slot()
    def _analyze_current_driver(self) -> None:
        """分析当前选中的司机（新增）"""
        if not self.current_driver_id:
            return
            
        # 显示进度对话框
        progress = QProgressDialog("正在分析驾驶行为...", "取消", 0, 100, self)
        progress.setWindowTitle("分析中")
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(10)
        
        # 启动分析
        self.improvement_system.queue_analysis_task(self.current_driver_id, self.current_time_range)
        
        # 模拟进度更新
        def update_progress():
            value = progress.value()
            if value < 90:
                progress.setValue(value + 5)
                QTimer.singleShot(500, update_progress)
        
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, update_progress)
        
        # 连接分析完成信号更新进度
        def on_analysis_completed(driver_id):
            if driver_id == self.current_driver_id:
                progress.setValue(100)
                self._load_analysis_data()
        
        self.improvement_system.improvement_analysis_completed.connect(on_analysis_completed)
        
        progress.exec_()

    @Slot(str)
    def _on_analysis_completed(self, driver_id: str) -> None:
        """分析完成处理（新增）"""
        if self.current_driver_id == driver_id:
            self._load_analysis_data()
