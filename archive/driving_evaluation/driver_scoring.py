"""司机评分系统模块（负责司机驾驶行为评分和等级评定）"""
import logging
import time
import datetime
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Union
from PySide6.QtCore import QObject, Signal, Slot, QMutex, QMutexLocker, QThread
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QLabel, QComboBox, QDateEdit, QPushButton, QGroupBox,
                             QFormLayout, QLineEdit, QDoubleSpinBox, QDialog, QDialogButtonBox,
                             QTabWidget, QChart, QChartView, QPieSeries, QBarSeries, QBarSet, 
                             QCategoryAxis, QValueAxis, QSplineSeries, QDateTimeAxis)
from PySide6.QtGui import QPainter, QColor, Qt

class DriverScoringSystem(QObject):
    """司机评分系统（保持原有类名）"""
    # 信号定义
    scores_updated = Signal(list)  # 评分更新信号
    scoring_completed = Signal(str)  # 评分计算完成信号（司机ID）
    error_occurred = Signal(str)  # 错误信号
    
    def __init__(self, core_services):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.core_services = core_services  # 核心服务引用
        
        # 线程安全锁
        self.scores_lock = QMutex()
        
        # 司机评分缓存
        self.driver_scores: Dict[str, Dict[str, Any]] = {}
        
        # 评分计算任务队列
        self.scoring_queue: List[Tuple[str, str]] = []  # (司机ID, 时间范围: daily, weekly, monthly)
        self.scoring_in_progress: Dict[str, bool] = {}
        
        # 加载评分配置
        self._load_scoring_config()
        
        # 连接配置变更信号
        self.core_services.config_manager.config_changed.connect(self._on_config_changed)
        
        # 启动评分计算线程
        self._start_scoring_thread()

    def _load_scoring_config(self) -> None:
        """加载评分配置（新增）"""
        # 从配置管理器获取评分相关配置
        config = self.core_services.config_manager.get_config('driver_scoring', {})
        
        # 评分项目及权重
        self.scoring_items = config.get('items', {
            'safe_speed': {
                'weight': 0.3,  # 权重
                'name': '安全车速',
                'description': '遵守速度限制的程度'
            },
            'smooth_acceleration': {
                'weight': 0.2,
                'name': '平稳加速',
                'description': '加速行为的平稳性'
            },
            'gentle_braking': {
                'weight': 0.2,
                'name': '平稳刹车',
                'description': '刹车行为的平稳性'
            },
            'lane_discipline': {
                'weight': 0.15,
                'name': '车道规范',
                'description': '保持车道和规范变道的程度'
            },
            'compliance': {
                'weight': 0.15,
                'name': '交通规则遵守',
                'description': '遵守交通规则的程度'
            }
        })
        
        # 评分等级划分
        self.grade_thresholds = config.get('grade_thresholds', {
            'S': 90,    # 优秀
            'A': 80,    # 良好
            'B': 70,    # 一般
            'C': 60,    # 合格
            'D': 0      # 不合格
        })
        
        # 评分计算参数
        self.scoring_parameters = config.get('parameters', {
            'max_score': 100,
            'min_score': 0,
            'penalty_factor': 1.5,  # 违规行为的惩罚系数
            'reward_factor': 1.2,   # 优秀行为的奖励系数
            'history_window_days': {
                'daily': 1,
                'weekly': 7,
                'monthly': 30,
                'overall': 90
            }
        })
        
        # 评分计算周期（秒）
        self.scoring_interval = config.get('scoring_interval', 86400)  # 默认每天计算一次

    def _start_scoring_thread(self) -> None:
        """启动评分计算线程（新增）"""
        self.scoring_thread = DriverScoringThread(self)
        self.scoring_thread.start()

    def calculate_driver_score(self, driver_id: str, time_range: str = 'weekly') -> Optional[Dict[str, Any]]:
        """计算司机评分（保持原有方法）"""
        if not driver_id:
            self.logger.error("司机ID不能为空")
            return None
            
        # 检查是否正在计算
        with QMutexLocker(self.scores_lock):
            if driver_id in self.scoring_in_progress and self.scoring_in_progress[driver_id]:
                self.logger.info(f"司机 {driver_id} 的评分正在计算中")
                return None
                
            # 标记为计算中
            self.scoring_in_progress[driver_id] = True
        
        try:
            self.logger.info(f"开始计算司机 {driver_id} 的{time_range}评分")
            
            # 获取司机信息
            driver_info = self.core_services.driver_manager.get_driver_info(driver_id)
            if not driver_info:
                self.logger.error(f"司机 {driver_id} 不存在")
                return None
                
            driver_name = driver_info.get('name', driver_id)
            
            # 确定时间范围
            window_days = self.scoring_parameters['history_window_days'].get(
                time_range, self.scoring_parameters['history_window_days']['weekly']
            )
            
            end_time = time.time()
            start_time = end_time - (window_days * 86400)
            
            # 获取该时间段内的驾驶行为数据
            driving_data = self.core_services.storage_manager.get_driver_behavior_data(
                driver_id=driver_id,
                start_time=start_time,
                end_time=end_time
            )
            
            if not driving_data or len(driving_data) < 5:  # 至少需要5条数据才能计算有意义的评分
                self.logger.warning(f"司机 {driver_id} 在指定时间范围内数据不足，无法计算有效评分")
                
                with QMutexLocker(self.scores_lock):
                    self.scoring_in_progress[driver_id] = False
                
                return None
            
            # 转换为DataFrame便于处理
            df = pd.DataFrame(driving_data)
            
            # 计算各项评分
            scores = self._calculate_item_scores(df)
            
            # 计算总评分（加权求和）
            total_score = 0.0
            for item, details in self.scoring_items.items():
                total_score += scores[item]['score'] * details['weight']
            
            # 限制在评分范围内
            total_score = max(
                self.scoring_parameters['min_score'],
                min(self.scoring_parameters['max_score'], total_score)
            )
            
            # 确定等级
            grade = self._determine_grade(total_score)
            
            # 获取风险告警次数
            alert_count = len(self.core_services.alert_manager.get_alert_history({
                'driver_id': driver_id,
                'start_time': start_time,
                'end_time': end_time
            }))
            
            # 应用风险告警惩罚
            if alert_count > 0:
                penalty = alert_count * 2  # 每次告警扣2分
                total_score = max(self.scoring_parameters['min_score'], total_score - penalty)
                # 重新确定等级
                grade = self._determine_grade(total_score)
            
            # 构建评分结果
            result = {
                'driver_id': driver_id,
                'driver_name': driver_name,
                'time_range': time_range,
                'window_days': window_days,
                'start_time': start_time,
                'end_time': end_time,
                'start_time_str': datetime.datetime.fromtimestamp(start_time).strftime("%Y-%m-%d"),
                'end_time_str': datetime.datetime.fromtimestamp(end_time).strftime("%Y-%m-%d"),
                'total_score': round(total_score, 1),
                'grade': grade,
                'items': scores,
                'alert_count': alert_count,
                'data_points': len(driving_data),
                'calculated_time': time.time(),
                'calculated_time_str': datetime.datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # 保存到缓存
            with QMutexLocker(self.scores_lock):
                if driver_id not in self.driver_scores:
                    self.driver_scores[driver_id] = {}
                self.driver_scores[driver_id][time_range] = result
            
            self.logger.info(f"司机 {driver_id} 的{time_range}评分计算完成: {total_score}分，等级{grade}")
            
            # 发出完成信号
            self.scoring_completed.emit(driver_id)
            
            return result
            
        except Exception as e:
            error_msg = f"计算司机 {driver_id} 评分失败: {str(e)}"
            self.logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return None
        finally:
            # 标记为计算完成
            with QMutexLocker(self.scores_lock):
                if driver_id in self.scoring_in_progress:
                    self.scoring_in_progress[driver_id] = False

    def _calculate_item_scores(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """计算各项评分（新增）"""
        scores = {}
        
        # 1. 安全车速评分
        # 基于超速频率和超速程度计算
        if 'speed' in df.columns and 'speed_limit' in df.columns:
            # 计算超速次数和平均超速比例
            speeding_instances = df[df['speed'] > df['speed_limit']]
            speeding_count = len(speeding_instances)
            total_instances = len(df)
            
            if total_instances > 0:
                speeding_ratio = speeding_count / total_instances
                
                # 计算平均超速百分比
                if speeding_count > 0:
                    speed_excess = (speeding_instances['speed'] - speeding_instances['speed_limit']) / speeding_instances['speed_limit']
                    avg_speed_excess = speed_excess.mean()
                else:
                    avg_speed_excess = 0
                
                # 安全车速评分（基础分100，根据超速情况扣分）
                score = 100 - (speeding_ratio * 100 * 3) - (avg_speed_excess * 100)
                score = max(0, min(100, score))
                
                # 评分说明
                if speeding_ratio == 0:
                    comment = "优秀：全程未超速"
                elif speeding_ratio < 0.05:
                    comment = "良好：偶尔轻微超速"
                elif speeding_ratio < 0.1:
                    comment = "一般：存在少量超速行为"
                else:
                    comment = "较差：频繁超速或严重超速"
                
                scores['safe_speed'] = {
                    'score': round(score, 1),
                    'comment': comment,
                    'details': {
                        'speeding_ratio': round(speeding_ratio * 100, 1),
                        'avg_speed_excess': round(avg_speed_excess * 100, 1),
                        'speeding_count': speeding_count
                    }
                }
            else:
                scores['safe_speed'] = {'score': 0, 'comment': '无数据', 'details': {}}
        else:
            scores['safe_speed'] = {'score': 0, 'comment': '数据不完整', 'details': {}}
        
        # 2. 平稳加速评分
        if 'acceleration' in df.columns:
            # 计算急加速次数（加速度超过2.5 m/s²视为急加速）
            harsh_accel_count = len(df[abs(df['acceleration']) > 2.5])
            total_instances = len(df)
            
            if total_instances > 0:
                harsh_accel_ratio = harsh_accel_count / total_instances
                
                # 计算平均加速度绝对值
                avg_accel = df['acceleration'].abs().mean()
                
                # 平稳加速评分
                score = 100 - (harsh_accel_ratio * 100 * 2) - (avg_accel * 10)
                score = max(0, min(100, score))
                
                # 评分说明
                if harsh_accel_ratio == 0 and avg_accel < 0.5:
                    comment = "优秀：加速非常平稳"
                elif harsh_accel_ratio < 0.03 and avg_accel < 1:
                    comment = "良好：加速较平稳"
                elif harsh_accel_ratio < 0.07 and avg_accel < 1.5:
                    comment = "一般：存在少量急加速"
                else:
                    comment = "较差：频繁急加速"
                
                scores['smooth_acceleration'] = {
                    'score': round(score, 1),
                    'comment': comment,
                    'details': {
                        'harsh_accel_ratio': round(harsh_accel_ratio * 100, 1),
                        'avg_accel': round(avg_accel, 2),
                        'harsh_accel_count': harsh_accel_count
                    }
                }
            else:
                scores['smooth_acceleration'] = {'score': 0, 'comment': '无数据', 'details': {}}
        else:
            scores['smooth_acceleration'] = {'score': 0, 'comment': '数据不完整', 'details': {}}
        
        # 3. 平稳刹车评分
        if 'braking_force' in df.columns:
            # 计算急刹车次数（刹车力超过0.8g视为急刹车）
            harsh_braking_count = len(df[df['braking_force'] > 0.8])
            total_instances = len(df)
            
            if total_instances > 0:
                harsh_braking_ratio = harsh_braking_count / total_instances
                
                # 计算平均刹车力
                avg_braking = df['braking_force'].mean()
                
                # 平稳刹车评分
                score = 100 - (harsh_braking_ratio * 100 * 2) - (avg_braking * 50)
                score = max(0, min(100, score))
                
                # 评分说明
                if harsh_braking_ratio == 0 and avg_braking < 0.3:
                    comment = "优秀：刹车非常平稳"
                elif harsh_braking_ratio < 0.03 and avg_braking < 0.4:
                    comment = "良好：刹车较平稳"
                elif harsh_braking_ratio < 0.07 and avg_braking < 0.5:
                    comment = "一般：存在少量急刹车"
                else:
                    comment = "较差：频繁急刹车"
                
                scores['gentle_braking'] = {
                    'score': round(score, 1),
                    'comment': comment,
                    'details': {
                        'harsh_braking_ratio': round(harsh_braking_ratio * 100, 1),
                        'avg_braking': round(avg_braking, 2),
                        'harsh_braking_count': harsh_braking_count
                    }
                }
            else:
                scores['gentle_braking'] = {'score': 0, 'comment': '无数据', 'details': {}}
        else:
            scores['gentle_braking'] = {'score': 0, 'comment': '数据不完整', 'details': {}}
        
        # 4. 车道规范评分
        if 'lane_deviation' in df.columns and 'lane_changes' in df.columns:
            # 计算车道偏离次数
            deviation_count = len(df[df['lane_deviation'] > 0.5])  # 偏离超过0.5米
            total_lane_changes = df['lane_changes'].sum() if 'lane_changes' in df.columns else 0
            driving_time = (df['timestamp'].max() - df['timestamp'].min()) / 3600 if len(df) > 1 else 0
            
            # 变道频率（每小时）
            lane_change_freq = total_lane_changes / driving_time if driving_time > 0 else 0
            
            # 车道规范评分
            score = 100 - (deviation_count * 0.5) - (lane_change_freq * 2)
            score = max(0, min(100, score))
            
            # 评分说明
            if deviation_count == 0 and lane_change_freq < 5:
                comment = "优秀：车道保持良好，变道适度"
            elif deviation_count < 10 and lane_change_freq < 10:
                comment = "良好：偶尔偏离车道，变道合理"
            elif deviation_count < 20 and lane_change_freq < 15:
                comment = "一般：存在一定车道偏离，变道略频繁"
            else:
                comment = "较差：频繁偏离车道，变道过于频繁"
            
            scores['lane_discipline'] = {
                'score': round(score, 1),
                'comment': comment,
                'details': {
                    'deviation_count': deviation_count,
                    'total_lane_changes': total_lane_changes,
                    'lane_change_freq': round(lane_change_freq, 1)
                }
            }
        else:
            scores['lane_discipline'] = {'score': 0, 'comment': '数据不完整', 'details': {}}
        
        # 5. 交通规则遵守评分
        # 基于交通违规次数、闯红灯等行为
        violation_count = 0
        violation_details = {}
        
        if 'traffic_violations' in df.columns:
            # 统计各类交通违规
            for violations in df['traffic_violations']:
                if isinstance(violations, list):
                    violation_count += len(violations)
                    for v in violations:
                        v_type = v.get('type', 'unknown')
                        violation_details[v_type] = violation_details.get(v_type, 0) + 1
        
        # 交通规则遵守评分
        score = 100 - (violation_count * 5)
        score = max(0, min(100, score))
        
        # 评分说明
        if violation_count == 0:
            comment = "优秀：无交通违规行为"
        elif violation_count < 3:
            comment = "良好：少量轻微违规"
        elif violation_count < 5:
            comment = "一般：存在一定违规行为"
        else:
            comment = "较差：多次违规，需重点关注"
        
        scores['compliance'] = {
            'score': round(score, 1),
            'comment': comment,
            'details': {
                'violation_count': violation_count,
                'violation_types': violation_details
            }
        }
        
        return scores

    def _determine_grade(self, score: float) -> str:
        """根据总分确定等级（新增）"""
        # 按等级从高到低检查
        if score >= self.grade_thresholds['S']:
            return 'S'
        elif score >= self.grade_thresholds['A']:
            return 'A'
        elif score >= self.grade_thresholds['B']:
            return 'B'
        elif score >= self.grade_thresholds['C']:
            return 'C'
        else:
            return 'D'

    def get_driver_score(self, driver_id: str, time_range: str = 'weekly') -> Optional[Dict[str, Any]]:
        """获取司机评分（新增）"""
        with QMutexLocker(self.scores_lock):
            # 检查缓存中是否存在且未过期（2小时内）
            if driver_id in self.driver_scores and time_range in self.driver_scores[driver_id]:
                score_data = self.driver_scores[driver_id][time_range]
                if time.time() - score_data['calculated_time'] < 7200:  # 2小时
                    return score_data
        
        # 缓存不存在或已过期，触发计算
        self.queue_scoring_task(driver_id, time_range)
        return None

    def get_drivers_ranking(self, time_range: str = 'weekly', top_n: int = 10) -> List[Dict[str, Any]]:
        """获取司机排名（新增）"""
        with QMutexLocker(self.scores_lock):
            # 收集所有司机的评分
            all_scores = []
            for driver_id, time_scores in self.driver_scores.items():
                if time_range in time_scores:
                    # 检查评分是否过期
                    if time.time() - time_scores[time_range]['calculated_time'] < 7200:
                        all_scores.append(time_scores[time_range])
            
            # 按总分排序
            all_scores.sort(key=lambda x: x['total_score'], reverse=True)
            
            # 返回前N名或全部
            return all_scores[:top_n] if top_n > 0 else all_scores

    def queue_scoring_task(self, driver_id: str, time_range: str = 'weekly') -> None:
        """排队评分计算任务（新增）"""
        with QMutexLocker(self.scores_lock):
            # 检查是否已在队列中
            for task in self.scoring_queue:
                if task[0] == driver_id and task[1] == time_range:
                    return  # 已在队列中，无需重复添加
            
            # 添加到队列
            self.scoring_queue.append((driver_id, time_range))
            self.logger.info(f"司机 {driver_id} 的{time_range}评分任务已加入队列")

    def calculate_all_drivers_scores(self, time_range: str = 'weekly') -> None:
        """计算所有司机的评分（新增）"""
        # 获取所有司机ID
        drivers = self.core_services.driver_manager.get_all_drivers()
        driver_ids = [d['id'] for d in drivers]
        
        # 添加到评分队列
        with QMutexLocker(self.scores_lock):
            for driver_id in driver_ids:
                # 检查是否已在队列中
                exists = False
                for task in self.scoring_queue:
                    if task[0] == driver_id and task[1] == time_range:
                        exists = True
                        break
                
                if not exists:
                    self.scoring_queue.append((driver_id, time_range))
        
        self.logger.info(f"已将 {len(driver_ids)} 名司机的{time_range}评分任务加入队列")

    def get_grade_distribution(self, time_range: str = 'weekly') -> Dict[str, int]:
        """获取等级分布统计（新增）"""
        distribution = {
            'S': 0,
            'A': 0,
            'B': 0,
            'C': 0,
            'D': 0
        }
        
        with QMutexLocker(self.scores_lock):
            for driver_id, time_scores in self.driver_scores.items():
                if time_range in time_scores:
                    # 检查评分是否过期
                    if time.time() - time_scores[time_range]['calculated_time'] < 7200:
                        grade = time_scores[time_range]['grade']
                        if grade in distribution:
                            distribution[grade] += 1
        
        return distribution

    def get_score_improvement(self, driver_id: str, previous_range: str = 'weekly', current_range: str = 'weekly') -> Optional[Dict[str, Any]]:
        """获取司机评分改进情况（新增）"""
        with QMutexLocker(self.scores_lock):
            if driver_id not in self.driver_scores:
                return None
                
            # 获取之前的评分
            if previous_range not in self.driver_scores[driver_id]:
                return None
            previous_score = self.driver_scores[driver_id][previous_range]
            
            # 获取当前的评分
            if current_range not in self.driver_scores[driver_id]:
                return None
            current_score = self.driver_scores[driver_id][current_range]
        
        # 计算改进情况
        total_change = current_score['total_score'] - previous_score['total_score']
        improvement_rate = (total_change / previous_score['total_score'] * 100) if previous_score['total_score'] > 0 else 0
        
        # 计算各项变化
        items_change = {}
        for item in self.scoring_items:
            if item in previous_score['items'] and item in current_score['items']:
                prev_item_score = previous_score['items'][item]['score']
                curr_item_score = current_score['items'][item]['score']
                items_change[item] = {
                    'previous': prev_item_score,
                    'current': curr_item_score,
                    'change': curr_item_score - prev_item_score,
                    'change_rate': (curr_item_score - prev_item_score) / prev_item_score * 100 if prev_item_score > 0 else 0
                }
        
        return {
            'driver_id': driver_id,
            'driver_name': current_score['driver_name'],
            'previous_range': previous_range,
            'current_range': current_range,
            'previous_score': previous_score['total_score'],
            'current_score': current_score['total_score'],
            'total_change': round(total_change, 1),
            'improvement_rate': round(improvement_rate, 1),
            'previous_grade': previous_score['grade'],
            'current_grade': current_score['grade'],
            'items_change': items_change,
            'previous_period': f"{previous_score['start_time_str']} 至 {previous_score['end_time_str']}",
            'current_period': f"{current_score['start_time_str']} 至 {current_score['end_time_str']}"
        }

    @Slot(str, Any, Any)
    def _on_config_changed(self, path: str, old_value: Any, new_value: Any) -> None:
        """处理配置变更（新增）"""
        if path.startswith('driver_scoring.'):
            self.logger.info(f"司机评分配置变更: {path}")
            self._load_scoring_config()
            
            # 配置变更后重新计算所有评分
            self.calculate_all_drivers_scores()


class DriverScoringThread(QThread):
    """司机评分计算线程（新增）"""
    def __init__(self, scoring_system: DriverScoringSystem):
        super().__init__()
        self.scoring_system = scoring_system
        self.logger = logging.getLogger(__name__)
        self.running = True
        self.check_interval = 60  # 检查间隔，秒

    def run(self) -> None:
        """运行评分计算线程"""
        self.logger.info("司机评分计算线程已启动")
        
        try:
            while self.running:
                # 检查任务队列
                task = None
                with QMutexLocker(self.scoring_system.scores_lock):
                    if self.scoring_system.scoring_queue:
                        task = self.scoring_system.scoring_queue.pop(0)
                
                if task:
                    driver_id, time_range = task
                    self.logger.info(f"处理评分任务: 司机 {driver_id}, 时间范围 {time_range}")
                    
                    # 计算评分
                    self.scoring_system.calculate_driver_score(driver_id, time_range)
                else:
                    # 没有任务，休眠
                    for _ in range(self.check_interval):
                        if not self.running:
                            break
                        time.sleep(1)
                
                # 定期触发所有司机的评分计算（每天一次）
                current_hour = datetime.datetime.now().hour
                if current_hour == 1 and datetime.datetime.now().minute < 5:  # 凌晨1点左右
                    self.logger.info("触发每日司机评分计算")
                    self.scoring_system.calculate_all_drivers_scores('daily')
                    # 每周一计算周评分
                    if datetime.datetime.now().weekday() == 0:  # 0表示周一
                        self.logger.info("触发每周司机评分计算")
                        self.scoring_system.calculate_all_drivers_scores('weekly')
                    # 每月1日计算月评分
                    if datetime.datetime.now().day == 1:
                        self.logger.info("触发每月司机评分计算")
                        self.scoring_system.calculate_all_drivers_scores('monthly')
                    
                    # 避免重复触发，休眠10分钟
                    time.sleep(600)
                
        except Exception as e:
            self.logger.error(f"司机评分计算线程错误: {str(e)}")
        finally:
            self.logger.info("司机评分计算线程已停止")

    def stop(self) -> None:
        """停止评分计算线程"""
        self.running = False
        self.wait()


class DriverScoreboardWidget(QWidget):
    """司机评分排行榜界面组件（新增）"""
    def __init__(self, scoring_system: DriverScoringSystem, core_services, parent=None):
        super().__init__(parent)
        self.scoring_system = scoring_system
        self.core_services = core_services
        self.logger = logging.getLogger(__name__)
        
        # 当前时间范围
        self.current_time_range = 'weekly'
        
        # 初始化UI
        self._init_ui()
        
        # 连接信号
        self._connect_signals()
        
        # 加载评分数据
        self._load_scoreboard_data()

    def _init_ui(self) -> None:
        """初始化UI组件（新增）"""
        self.setWindowTitle("司机评分排行榜")
        self.resize(1000, 700)
        
        main_layout = QVBoxLayout(self)
        
        # 控制区域
        control_layout = QHBoxLayout()
        
        # 时间范围选择
        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems(['daily', 'weekly', 'monthly', 'overall'])
        self.time_range_combo.setCurrentText('weekly')
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新评分")
        
        # 计算所有评分按钮
        self.calculate_all_btn = QPushButton("计算所有评分")
        
        # 显示数量选择
        self.top_n_combo = QComboBox()
        self.top_n_combo.addItems(['10', '20', '50', '全部'])
        self.top_n_combo.setCurrentText('10')
        
        control_layout.addWidget(QLabel("时间范围:"))
        control_layout.addWidget(self.time_range_combo)
        control_layout.addSpacing(10)
        control_layout.addWidget(self.refresh_btn)
        control_layout.addWidget(self.calculate_all_btn)
        control_layout.addSpacing(20)
        control_layout.addWidget(QLabel("显示数量:"))
        control_layout.addWidget(self.top_n_combo)
        control_layout.addStretch()
        
        main_layout.addLayout(control_layout)
        
        # 统计和图表区域
        stats_chart_layout = QHBoxLayout()
        
        # 统计信息
        stats_group = QGroupBox("评分统计")
        stats_layout = QFormLayout()
        
        self.total_drivers_label = QLabel("0")
        self.avg_score_label = QLabel("0.0")
        self.s_grade_label = QLabel("0")
        self.a_grade_label = QLabel("0")
        self.b_grade_label = QLabel("0")
        self.c_grade_label = QLabel("0")
        self.d_grade_label = QLabel("0")
        
        # 设置等级标签样式
        self.s_grade_label.setStyleSheet("color: #d32f2f; font-weight: bold;")  # 红色
        self.a_grade_label.setStyleSheet("color: #ff9800; font-weight: bold;")  # 橙色
        self.b_grade_label.setStyleSheet("color: #ffeb3b; font-weight: bold;")  # 黄色
        self.c_grade_label.setStyleSheet("color: #4caf50; font-weight: bold;")  # 绿色
        self.d_grade_label.setStyleSheet("color: #9e9e9e; font-weight: bold;")  # 灰色
        
        stats_layout.addRow("司机总数:", self.total_drivers_label)
        stats_layout.addRow("平均评分:", self.avg_score_label)
        stats_layout.addRow("S级司机:", self.s_grade_label)
        stats_layout.addRow("A级司机:", self.a_grade_label)
        stats_layout.addRow("B级司机:", self.b_grade_label)
        stats_layout.addRow("C级司机:", self.c_grade_label)
        stats_layout.addRow("D级司机:", self.d_grade_label)
        
        stats_group.setLayout(stats_layout)
        stats_chart_layout.addWidget(stats_group, 1)
        
        # 等级分布图表
        self.grade_chart = QChart()
        self.grade_chart.setTitle("司机等级分布")
        self.grade_chart_view = QChartView(self.grade_chart)
        self.grade_chart_view.setRenderHint(QPainter.Antialiasing)
        
        stats_chart_layout.addWidget(self.grade_chart_view, 2)
        
        main_layout.addLayout(stats_chart_layout)
        
        # 评分表格
        self.score_table = QTableWidget()
        self.score_table.setColumnCount(7)
        self.score_table.setHorizontalHeaderLabels([
            "排名", "司机ID", "司机姓名", "总评分", "等级", "告警次数", "数据点数量"
        ])
        self.score_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.score_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.score_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        main_layout.addWidget(self.score_table)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        self.details_btn = QPushButton("查看详情")
        
        btn_layout.addWidget(self.details_btn)
        btn_layout.addStretch()
        
        main_layout.addLayout(btn_layout)

    def _connect_signals(self) -> None:
        """连接信号与槽（新增）"""
        # 评分更新信号
        self.scoring_system.scores_updated.connect(self._load_scoreboard_data)
        self.scoring_system.scoring_completed.connect(self._on_scoring_completed)
        
        # 按钮信号
        self.refresh_btn.clicked.connect(self._load_scoreboard_data)
        self.calculate_all_btn.clicked.connect(self._calculate_all_scores)
        self.time_range_combo.currentTextChanged.connect(self._on_time_range_changed)
        self.top_n_combo.currentTextChanged.connect(self._load_scoreboard_data)
        self.details_btn.clicked.connect(self._view_driver_details)
        
        # 表格双击事件
        self.score_table.cellDoubleClicked.connect(self._on_cell_double_clicked)

    def _on_time_range_changed(self, time_range: str) -> None:
        """时间范围变更处理（新增）"""
        self.current_time_range = time_range
        self._load_scoreboard_data()

    def _load_scoreboard_data(self) -> None:
        """加载评分排行榜数据（新增）"""
        # 获取显示数量
        top_n_text = self.top_n_combo.currentText()
        top_n = int(top_n_text) if top_n_text != '全部' else 0
        
        # 获取司机排名
        ranking = self.scoring_system.get_drivers_ranking(self.current_time_range, top_n)
        
        # 更新表格
        self.score_table.setRowCount(len(ranking))
        
        total_score = 0.0
        
        for row, driver_score in enumerate(ranking):
            total_score += driver_score['total_score']
            
            # 排名
            self.score_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            
            # 司机ID
            self.score_table.setItem(row, 1, QTableWidgetItem(driver_score['driver_id']))
            
            # 司机姓名
            self.score_table.setItem(row, 2, QTableWidgetItem(driver_score['driver_name']))
            
            # 总评分
            score_item = QTableWidgetItem(f"{driver_score['total_score']}")
            # 设置评分颜色
            score = driver_score['total_score']
            if score >= 90:
                score_item.setForeground(QColor("#d32f2f"))  # 红色
            elif score >= 80:
                score_item.setForeground(QColor("#ff9800"))  # 橙色
            elif score >= 70:
                score_item.setForeground(QColor("#ffeb3b"))  # 黄色
            elif score >= 60:
                score_item.setForeground(QColor("#4caf50"))  # 绿色
            else:
                score_item.setForeground(QColor("#9e9e9e"))  # 灰色
            self.score_table.setItem(row, 3, score_item)
            
            # 等级
            grade_item = QTableWidgetItem(driver_score['grade'])
            # 设置等级颜色和背景
            if driver_score['grade'] == 'S':
                grade_item.setForeground(QColor("#d32f2f"))
                grade_item.setBackground(QColor("#ffebee"))
            elif driver_score['grade'] == 'A':
                grade_item.setForeground(QColor("#ff9800"))
                grade_item.setBackground(QColor("#fff3e0"))
            elif driver_score['grade'] == 'B':
                grade_item.setForeground(QColor("#ffeb3b"))
                grade_item.setBackground(QColor("#fffde7"))
            elif driver_score['grade'] == 'C':
                grade_item.setForeground(QColor("#4caf50"))
                grade_item.setBackground(QColor("#e8f5e9"))
            else:  # D
                grade_item.setForeground(QColor("#9e9e9e"))
                grade_item.setBackground(QColor("#f5f5f5"))
            self.score_table.setItem(row, 4, grade_item)
            
            # 告警次数
            alert_item = QTableWidgetItem(str(driver_score['alert_count']))
            if driver_score['alert_count'] > 0:
                alert_item.setForeground(QColor("#f44336"))  # 红色
            self.score_table.setItem(row, 5, alert_item)
            
            # 数据点数量
            self.score_table.setItem(row, 6, QTableWidgetItem(str(driver_score['data_points'])))
        
        # 更新统计信息
        driver_count = len(ranking)
        self.total_drivers_label.setText(str(driver_count))
        
        avg_score = total_score / driver_count if driver_count > 0 else 0
        self.avg_score_label.setText(f"{avg_score:.1f}")
        
        # 获取等级分布
        distribution = self.scoring_system.get_grade_distribution(self.current_time_range)
        self.s_grade_label.setText(str(distribution['S']))
        self.a_grade_label.setText(str(distribution['A']))
        self.b_grade_label.setText(str(distribution['B']))
        self.c_grade_label.setText(str(distribution['C']))
        self.d_grade_label.setText(str(distribution['D']))
        
        # 更新等级分布图表
        self._update_grade_chart(distribution)

    def _update_grade_chart(self, distribution: Dict[str, int]) -> None:
        """更新等级分布图表（新增）"""
        # 清除现有系列
        self.grade_chart.removeAllSeries()
        
        # 创建饼图系列
        series = QPieSeries()
        
        # 定义颜色
        colors = {
            'S': QColor("#d32f2f"),
            'A': QColor("#ff9800"),
            'B': QColor("#ffeb3b"),
            'C': QColor("#4caf50"),
            'D': QColor("#9e9e9e")
        }
        
        # 添加数据
        for grade, count in distribution.items():
            if count > 0:
                slice = series.append(f"{grade}级 ({count})", count)
                slice.setColor(colors[grade])
                slice.setLabelVisible(True)
        
        # 添加到图表
        self.grade_chart.addSeries(series)

    @Slot()
    def _calculate_all_scores(self) -> None:
        """计算所有司机评分（新增）"""
        self.scoring_system.calculate_all_drivers_scores(self.current_time_range)
        
        # 显示提示
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "计算任务已启动", 
            f"已开始计算所有司机的{self.current_time_range}评分，"
            "计算完成后将自动更新排行榜。"
        )

    @Slot(str)
    def _on_scoring_completed(self, driver_id: str) -> None:
        """评分计算完成处理（新增）"""
        # 刷新排行榜数据
        self._load_scoreboard_data()

    @Slot()
    def _view_driver_details(self) -> None:
        """查看选中司机的评分详情（新增）"""
        selected_rows = self.score_table.selectionModel().selectedRows()
        if not selected_rows:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "请先选择一个司机")
            return
            
        row = selected_rows[0].row()
        driver_id = self.score_table.item(row, 1).text()
        
        # 显示司机评分详情
        detail_dialog = DriverScoreDetailDialog(
            self.scoring_system, 
            self.core_services,
            driver_id,
            self.current_time_range,
            self
        )
        detail_dialog.exec_()

    @Slot(int, int)
    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        """表格单元格双击事件（查看详情）（新增）"""
        driver_id = self.score_table.item(row, 1).text()
        
        # 显示司机评分详情
        detail_dialog = DriverScoreDetailDialog(
            self.scoring_system, 
            self.core_services,
            driver_id,
            self.current_time_range,
            self
        )
        detail_dialog.exec_()


class DriverScoreDetailDialog(QDialog):
    """司机评分详情对话框（新增）"""
    def __init__(self, scoring_system: DriverScoringSystem, core_services, 
                 driver_id: str, time_range: str, parent=None):
        super().__init__(parent)
        self.scoring_system = scoring_system
        self.core_services = core_services
        self.driver_id = driver_id
        self.time_range = time_range
        
        # 获取司机评分数据
        self.score_data = self.scoring_system.get_driver_score(driver_id, time_range)
        
        # 如果没有数据，尝试计算
        if not self.score_data:
            self.scoring_system.queue_scoring_task(driver_id, time_range)
        
        # 初始化UI
        self._init_ui()
        
        # 连接信号
        self._connect_signals()
        
        # 加载详情数据
        self._load_detail_data()

    def _init_ui(self) -> None:
        """初始化UI组件（新增）"""
        self.setWindowTitle(f"司机评分详情 - {self.driver_id}")
        self.resize(1000, 700)
        
        main_layout = QVBoxLayout(self)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 总览标签页
        self.overview_tab = QWidget()
        self._init_overview_tab()
        self.tab_widget.addTab(self.overview_tab, "评分总览")
        
        # 分项评分标签页
        self.items_tab = QWidget()
        self._init_items_tab()
        self.tab_widget.addTab(self.items_tab, "分项评分")
        
        # 历史趋势标签页
        self.trend_tab = QWidget()
        self._init_trend_tab()
        self.tab_widget.addTab(self.trend_tab, "历史趋势")
        
        # 风险告警标签页
        self.alerts_tab = QWidget()
        self._init_alerts_tab()
        self.tab_widget.addTab(self.alerts_tab, "风险告警")
        
        main_layout.addWidget(self.tab_widget)
        
        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        main_layout.addWidget(buttons)

    def _init_overview_tab(self) -> None:
        """初始化总览标签页（新增）"""
        layout = QVBoxLayout(self.overview_tab)
        
        # 司机基本信息
        info_layout = QHBoxLayout()
        
        # 左侧：基本信息
        basic_info_group = QGroupBox("司机基本信息")
        basic_form = QFormLayout()
        
        self.driver_name_label = QLabel("")
        self.driver_id_label = QLabel(self.driver_id)
        self.employment_date_label = QLabel("")
        self.vehicle_label = QLabel("")
        
        basic_form.addRow("司机ID:", self.driver_id_label)
        basic_form.addRow("司机姓名:", self.driver_name_label)
        basic_form.addRow("入职日期:", self.employment_date_label)
        basic_form.addRow("所属车辆:", self.vehicle_label)
        
        basic_info_group.setLayout(basic_form)
        info_layout.addWidget(basic_info_group, 1)
        
        # 右侧：评分摘要
        score_summary_group = QGroupBox("评分摘要")
        summary_layout = QVBoxLayout()
        
        # 总评分和等级
        score_grade_layout = QHBoxLayout()
        
        self.total_score_label = QLabel("0")
        self.total_score_label.setStyleSheet("font-size: 48px; font-weight: bold;")
        
        self.grade_label = QLabel("")
        self.grade_label.setStyleSheet("font-size: 48px; font-weight: bold;")
        
        score_grade_layout.addWidget(self.total_score_label)
        score_grade_layout.addWidget(self.grade_label)
        score_grade_layout.addStretch()
        
        # 评分周期和数据点
        period_layout = QFormLayout()
        
        self.period_label = QLabel("")
        self.data_points_label = QLabel("")
        self.alert_count_label = QLabel("")
        
        period_layout.addRow("评分周期:", self.period_label)
        period_layout.addRow("数据点数量:", self.data_points_label)
        period_layout.addRow("风险告警次数:", self.alert_count_label)
        
        # 综合评价
        self.evaluation_label = QLabel("")
        self.evaluation_label.setWordWrap(True)
        
        summary_layout.addLayout(score_grade_layout)
        summary_layout.addLayout(period_layout)
        summary_layout.addWidget(QLabel("<strong>综合评价:</strong>"))
        summary_layout.addWidget(self.evaluation_label)
        summary_layout.addStretch()
        
        score_summary_group.setLayout(summary_layout)
        info_layout.addWidget(score_summary_group, 1)
        
        layout.addLayout(info_layout)
        
        # 评分分布图表
        chart_group = QGroupBox("评分分布")
        chart_layout = QVBoxLayout()
        
        self.score_distribution_chart = QChart()
        self.score_distribution_chart.setTitle("各项评分分布")
        self.score_distribution_chart_view = QChartView(self.score_distribution_chart)
        self.score_distribution_chart_view.setRenderHint(QPainter.Antialiasing)
        
        chart_layout.addWidget(self.score_distribution_chart_view)
        chart_group.setLayout(chart_layout)
        
        layout.addWidget(chart_group)
        
        layout.addStretch()

    def _init_items_tab(self) -> None:
        """初始化分项评分标签页（新增）"""
        layout = QVBoxLayout(self.items_tab)
        
        # 使用滚动区域
        from PySide6.QtWidgets import QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # 为每个评分项创建一个分组
        self.score_items_widgets = {}
        
        # 获取评分项定义
        scoring_items = self.scoring_system.scoring_items
        
        for item_key, item_info in scoring_items.items():
            group = QGroupBox(f"{item_info['name']} (权重: {item_info['weight']*100}%)")
            group.setToolTip(item_info['description'])
            
            item_layout = QVBoxLayout()
            
            # 评分和说明
            score_comment_layout = QHBoxLayout()
            
            score_label = QLabel("0")
            score_label.setStyleSheet("font-size: 24px; font-weight: bold;")
            
            comment_label = QLabel("")
            comment_label.setWordWrap(True)
            comment_label.setStyleSheet("color: #666;")
            
            score_comment_layout.addWidget(score_label, 1)
            score_comment_layout.addWidget(comment_label, 3)
            
            # 详细信息
            details_text = QLabel("")
            details_text.setWordWrap(True)
            
            item_layout.addLayout(score_comment_layout)
            item_layout.addWidget(QLabel("<strong>详细信息:</strong>"))
            item_layout.addWidget(details_text)
            
            group.setLayout(item_layout)
            content_layout.addWidget(group)
            
            # 保存控件引用
            self.score_items_widgets[item_key] = {
                'score_label': score_label,
                'comment_label': comment_label,
                'details_label': details_text
            }
        
        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

    def _init_trend_tab(self) -> None:
        """初始化历史趋势标签页（新增）"""
        layout = QVBoxLayout(self.trend_tab)
        
        # 时间范围选择
        time_range_layout = QHBoxLayout()
        
        self.trend_range_combo = QComboBox()
        self.trend_range_combo.addItems(['daily', 'weekly', 'monthly'])
        self.trend_range_combo.setCurrentText('weekly')
        
        time_range_layout.addWidget(QLabel("趋势周期:"))
        time_range_layout.addWidget(self.trend_range_combo)
        time_range_layout.addStretch()
        
        layout.addLayout(time_range_layout)
        
        # 趋势图表
        chart_group = QGroupBox("评分趋势")
        chart_layout = QVBoxLayout()
        
        self.trend_chart = QChart()
        self.trend_chart.setTitle("司机评分历史趋势")
        self.trend_chart_view = QChartView(self.trend_chart)
        self.trend_chart_view.setRenderHint(QPainter.Antialiasing)
        
        chart_layout.addWidget(self.trend_chart_view)
        chart_group.setLayout(chart_layout)
        
        layout.addWidget(chart_group)

    def _init_alerts_tab(self) -> None:
        """初始化风险告警标签页（新增）"""
        layout = QVBoxLayout(self.alerts_tab)
        
        # 告警表格
        self.alerts_table = QTableWidget()
        self.alerts_table.setColumnCount(5)
        self.alerts_table.setHorizontalHeaderLabels([
            "告警ID", "风险评分", "时间", "位置", "状态"
        ])
        self.alerts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.alerts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        layout.addWidget(self.alerts_table)

    def _connect_signals(self) -> None:
        """连接信号与槽（新增）"""
        # 评分更新信号
        self.scoring_system.scoring_completed.connect(self._on_scoring_completed)
        
        # 趋势周期变更
        self.trend_range_combo.currentTextChanged.connect(self._update_trend_chart)

    def _load_detail_data(self) -> None:
        """加载详情数据（新增）"""
        if not self.score_data:
            # 没有数据
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "提示", 
                f"司机 {self.driver_id} 的{self.time_range}评分数据正在计算中，"
                "请稍后刷新查看。"
            )
            return
        
        # 加载司机基本信息
        driver_info = self.core_services.driver_manager.get_driver_info(self.driver_id)
        if driver_info:
            self.driver_name_label.setText(driver_info.get('name', ''))
            self.employment_date_label.setText(
                datetime.datetime.fromtimestamp(driver_info.get('employment_date', 0)).strftime("%Y-%m-%d") 
                if driver_info.get('employment_date') else ''
            )
            self.vehicle_label.setText(driver_info.get('vehicle_id', '') or '未分配')
        
        # 更新评分摘要
        self.total_score_label.setText(f"{self.score_data['total_score']}")
        
        self.grade_label.setText(self.score_data['grade'])
        # 设置等级颜色
        grade_colors = {
            'S': "#d32f2f",
            'A': "#ff9800",
            'B': "#ffeb3b",
            'C': "#4caf50",
            'D': "#9e9e9e"
        }
        if self.score_data['grade'] in grade_colors:
            self.grade_label.setStyleSheet(f"font-size: 48px; font-weight: bold; color: {grade_colors[self.score_data['grade']]};")
        
        self.period_label.setText(f"{self.score_data['start_time_str']} 至 {self.score_data['end_time_str']}")
        self.data_points_label.setText(str(self.score_data['data_points']))
        self.alert_count_label.setText(str(self.score_data['alert_count']))
        
        # 设置综合评价
        self._set_evaluation_text()
        
        # 更新评分分布图表
        self._update_score_distribution_chart()
        
        # 更新分项评分
        self._update_score_items()
        
        # 更新趋势图表
        self._update_trend_chart()
        
        # 加载告警数据
        self._load_alerts_data()

    def _set_evaluation_text(self) -> None:
        """设置综合评价文本（新增）"""
        if not self.score_data:
            return
            
        score = self.score_data['total_score']
        grade = self.score_data['grade']
        
        # 根据评分设置不同的评价
        if grade == 'S':
            evaluation = (f"优秀！司机 {self.score_data['driver_name']} 的驾驶行为表现优异，"
                         f"各项指标均达到优秀水平。无明显风险行为，是其他司机的榜样。")
        elif grade == 'A':
            evaluation = (f"良好。司机 {self.score_data['driver_name']} 的驾驶行为总体良好，"
                         f"大部分指标表现优秀。偶尔有轻微不规范行为，但不构成严重风险。")
        elif grade == 'B':
            evaluation = (f"一般。司机 {self.score_data['driver_name']} 的驾驶行为基本符合规范，"
                         f"存在一些需要改进的地方。建议进行针对性培训，提高驾驶安全性。")
        elif grade == 'C':
            evaluation = (f"合格。司机 {self.score_data['driver_name']} 的驾驶行为刚好达到合格标准，"
                         f"存在较多不规范行为，有一定的安全风险。需要加强监管和培训。")
        else:  # D
            evaluation = (f"不合格！司机 {self.score_data['driver_name']} 的驾驶行为存在严重问题，"
                         f"风险评分较低，且有多次风险告警。建议立即进行约谈和再培训，"
                         "必要时暂停驾驶任务，待考核合格后方可上岗。")
        
        # 添加主要优点和不足
        items = self.score_data['items']
        sorted_items = sorted(items.items(), key=lambda x: x[1]['score'], reverse=True)
        
        # 优点（评分最高的两项）
        strengths = sorted_items[:2]
        strengths_text = ", ".join([
            f"{self.scoring_system.scoring_items[item]['name']}({score['score']}分)" 
            for item, score in strengths
        ])
        
        # 不足（评分最低的两项）
        weaknesses = sorted_items[-2:]
        weaknesses_text = ", ".join([
            f"{self.scoring_system.scoring_items[item]['name']}({score['score']}分)" 
            for item, score in weaknesses
        ])
        
        evaluation += f"\n\n主要优点：{strengths_text}"
        evaluation += f"\n需要改进：{weaknesses_text}"
        
        self.evaluation_label.setText(evaluation)

    def _update_score_distribution_chart(self) -> None:
        """更新评分分布图表（新增）"""
        if not self.score_data:
            return
            
        # 清除现有系列
        self.score_distribution_chart.removeAllSeries()
        
        # 创建柱状图系列
        series = QBarSeries()
        
        # 添加数据
        bar_set = QBarSet("评分")
        
        item_names = []
        item_scores = []
        
        for item_key, item_info in self.scoring_system.scoring_items.items():
            if item_key in self.score_data['items']:
                item_names.append(item_info['name'])
                item_scores.append(self.score_data['items'][item_key]['score'])
        
        bar_set.append(item_scores)
        series.append(bar_set)
        
        # 添加到图表
        self.score_distribution_chart.addSeries(series)
        
        # 创建坐标轴
        axis_x = QCategoryAxis()
        axis_x.appendCategories(item_names)
        self.score_distribution_chart.setAxisX(axis_x, series)
        
        axis_y = QValueAxis()
        axis_y.setRange(0, 100)
        axis_y.setTitleText("评分")
        self.score_distribution_chart.setAxisY(axis_y, series)

    def _update_score_items(self) -> None:
        """更新分项评分（新增）"""
        if not self.score_data:
            return
            
        for item_key, widgets in self.score_items_widgets.items():
            if item_key in self.score_data['items']:
                item_data = self.score_data['items'][item_key]
                
                # 更新评分
                widgets['score_label'].setText(f"{item_data['score']}")
                
                # 设置评分颜色
                score = item_data['score']
                if score >= 90:
                    widgets['score_label'].setStyleSheet("font-size: 24px; font-weight: bold; color: #d32f2f;")
                elif score >= 80:
                    widgets['score_label'].setStyleSheet("font-size: 24px; font-weight: bold; color: #ff9800;")
                elif score >= 70:
                    widgets['score_label'].setStyleSheet("font-size: 24px; font-weight: bold; color: #ffeb3b;")
                elif score >= 60:
                    widgets['score_label'].setStyleSheet("font-size: 24px; font-weight: bold; color: #4caf50;")
                else:
                    widgets['score_label'].setStyleSheet("font-size: 24px; font-weight: bold; color: #9e9e9e;")
                
                # 更新说明
                widgets['comment_label'].setText(item_data['comment'])
                
                # 更新详细信息
                details = []
                for key, value in item_data['details'].items():
                    # 转换为友好名称
                    key_name = key.replace('_', ' ').capitalize()
                    details.append(f"{key_name}: {value}")
                
                widgets['details_label'].setText("<br>".join(details))

    def _update_trend_chart(self) -> None:
        """更新趋势图表（新增）"""
        # 清除现有系列和坐标轴
        self.trend_chart.removeAllSeries()
        for axis in self.trend_chart.axes():
            self.trend_chart.removeAxis(axis)
        
        series = QSplineSeries()
        series.setName("总评分")
        
        periods = 6
        end_time = self.score_data['end_time'] if self.score_data else time.time()
        
        for i in range(periods):
            period_days = {
                'daily': 1,
                'weekly': 7,
                'monthly': 30
            }.get(self.trend_range_combo.currentText(), 7)
            
            timestamp = end_time - (periods - i - 1) * period_days * 86400
            
            if self.score_data:
                score = self.score_data['total_score']
            else:
                score = 0
            
            series.append(timestamp * 1000, score)
        
        self.trend_chart.addSeries(series)
        
        # 创建坐标轴
        axis_x = QDateTimeAxis()
        axis_x.setFormat("yyyy-MM-dd")
        axis_x.setTitleText("日期")
        self.trend_chart.setAxisX(axis_x, series)
        
        axis_y = QValueAxis()
        axis_y.setRange(0, 100)
        axis_y.setTitleText("评分")
        self.trend_chart.setAxisY(axis_y, series)

    def _load_alerts_data(self) -> None:
        """加载告警数据（新增）"""
        if not self.score_data:
            return
            
        # 获取该司机在评分周期内的告警
        alerts = self.core_services.alert_manager.get_alert_history({
            'driver_id': self.driver_id,
            'start_time': self.score_data['start_time'],
            'end_time': self.score_data['end_time']
        })
        
        # 更新表格
        self.alerts_table.setRowCount(len(alerts))
        
        for row, alert in enumerate(alerts):
            # 告警ID
            self.alerts_table.setItem(row, 0, QTableWidgetItem(alert['id']))
            
            # 风险评分
            score_item = QTableWidgetItem(f"{alert['risk_score']:.2f}")
            if alert['risk_score'] >= 0.8:
                score_item.setForeground(QColor("#f44336"))
            elif alert['risk_score'] >= 0.3:
                score_item.setForeground(QColor("#ff9800"))
            else:
                score_item.setForeground(QColor("#4caf50"))
            self.alerts_table.setItem(row, 1, score_item)
            
            # 时间
            self.alerts_table.setItem(row, 2, QTableWidgetItem(alert['timestamp_str']))
            
            # 位置
            self.alerts_table.setItem(row, 3, QTableWidgetItem(alert['location']))
            
            # 状态
            status_item = QTableWidgetItem(alert['status'])
            if alert['status'] == 'active':
                status_item.setForeground(QColor("#f44336"))
            elif alert['status'] == 'acknowledged':
                status_item.setForeground(QColor("#ff9800"))
            elif alert['status'] == 'resolved':
                status_item.setForeground(QColor("#4caf50"))
            self.alerts_table.setItem(row, 4, status_item)

    @Slot(str)
    def _on_scoring_completed(self, driver_id: str) -> None:
        """评分计算完成处理（新增）"""
        if driver_id == self.driver_id:
            # 更新评分数据
            self.score_data = self.scoring_system.get_driver_score(driver_id, self.time_range)
            # 重新加载详情
            self._load_detail_data()
