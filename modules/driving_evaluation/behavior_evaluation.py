"""驾驶行为评估模块（计算综合评分和趋势分析）"""
import logging
import time
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
from PySide6.QtCore import QObject, Signal, QMutex, QMutexLocker
from common.constants import (
    SEVERITY_WEIGHTS, BEHAVIOR_WEIGHTS,
    SCORE_LEVELS, EVALUATION_INTERVAL
)
from common.exceptions import BehaviorAnalysisError

class BehaviorEvaluator(QObject):
    """驾驶行为评估器（保持原有类名）"""
    # 信号定义（新增线程安全通知机制）
    evaluation_updated = Signal(dict)  # 评估结果更新信号
    trend_updated = Signal(list)       # 趋势数据更新信号

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # 线程安全锁（新增）
        self.evaluation_lock = QMutex()
        
        # 评估数据缓存（保持原有）
        self.recent_evaluations = []  # 最近评估结果
        self.behavior_counts = {      # 行为计数器
            'hard_acceleration': 0,
            'hard_braking': 0,
            'sharp_turning': 0,
            'overspeeding': 0
        }
        
        # 评估参数（保持原有）
        self.evaluation_window = 300  # 5分钟评估窗口（秒）
        self.max_history = 100        # 最大历史记录数
        
        # 评估状态（新增）
        self.is_evaluating = False

    def add_behavior_event(self, event: Dict[str, Any]) -> None:
        """添加行为事件到评估系统（线程安全）"""
        if 'event_type' not in event:
            return
            
        event_type = event['event_type']
        if event_type not in self.behavior_counts:
            return
            
        with QMutexLocker(self.evaluation_lock):  # 线程安全保护
            # 更新行为计数器
            self.behavior_counts[event_type] += 1
            
            # 定期触发评估（基于配置的时间间隔）
            current_time = time.time()
            if (not self.recent_evaluations or 
                current_time - self.recent_evaluations[-1]['timestamp'] > EVALUATION_INTERVAL):
                self._trigger_evaluation(current_time)

    def _trigger_evaluation(self, timestamp: float) -> None:
        """触发一次驾驶行为评估（保持原有逻辑）"""
        if self.is_evaluating:
            return
            
        self.is_evaluating = True
        try:
            # 计算综合评分
            score = self._calculate_overall_score()
            
            # 生成评估结果
            evaluation = {
                'timestamp': timestamp,
                'overall_score': round(score, 1),
                'level': self._get_score_level(score),
                'behavior_counts': self.behavior_counts.copy(),
                'details': self._get_evaluation_details(score)
            }
            
            # 保存评估结果
            with QMutexLocker(self.evaluation_lock):
                self.recent_evaluations.append(evaluation)
                # 限制历史记录数量
                if len(self.recent_evaluations) > self.max_history:
                    self.recent_evaluations.pop(0)
            
            # 发射评估更新信号
            self.evaluation_updated.emit(evaluation)
            
            # 计算并发射趋势数据
            trend_data = self._calculate_trend()
            self.trend_updated.emit(trend_data)
            
            self.logger.debug(f"驾驶行为评估完成，综合评分: {score}")
            
        except Exception as e:
            self.logger.error(f"评估计算失败: {str(e)}")
            raise BehaviorAnalysisError(f"评估计算失败: {str(e)}")
        finally:
            self.is_evaluating = False

    def _calculate_overall_score(self) -> float:
        """计算综合评分（保持原有算法）"""
        # 基础分为100分
        base_score = 100.0
        
        # 根据行为次数扣分（原有逻辑）
        total_deduction = 0.0
        for behavior, count in self.behavior_counts.items():
            # 行为权重 × 次数 × 严重程度权重
            deduction = count * BEHAVIOR_WEIGHTS[behavior] * SEVERITY_WEIGHTS[3]  # 使用平均严重度
            total_deduction += deduction
            
        # 计算最终得分（不低于0分）
        final_score = base_score - total_deduction
        return max(0.0, final_score)

    def _get_score_level(self, score: float) -> str:
        """获取评分等级（保持原有逻辑）"""
        for level, (min_score, _) in SCORE_LEVELS.items():
            if score >= min_score:
                return level
        return "差"

    def _get_evaluation_details(self, score: float) -> Dict[str, str]:
        """生成评估详情（保持原有逻辑）"""
        details = {}
        
        # 总体评价
        level = self._get_score_level(score)
        level_descriptions = {
            "优秀": "驾驶行为优异，几乎没有危险操作，继续保持！",
            "良好": "驾驶行为良好，偶有轻微不当操作，注意改进。",
            "一般": "驾驶行为一般，存在一些需要注意的问题。",
            "较差": "驾驶行为较差，存在较多危险操作，需立即改进。",
            "差": "驾驶行为危险，存在大量不安全操作，建议接受培训。"
        }
        details['overall_comment'] = level_descriptions.get(level, "需要改进驾驶习惯。")
        
        # 主要问题
        problematic_behaviors = []
        for behavior, count in self.behavior_counts.items():
            if count > 5:  # 超过5次视为需要关注的问题
                behavior_names = {
                    'hard_acceleration': '急加速',
                    'hard_braking': '急刹车',
                    'sharp_turning': '急转弯',
                    'overspeeding': '超速'
                }
                problematic_behaviors.append(f"{behavior_names[behavior]}({count}次)")
        
        if problematic_behaviors:
            details['main_issues'] = f"主要问题: {', '.join(problematic_behaviors)}"
        else:
            details['main_issues'] = "无明显问题"
            
        return details

    def _calculate_trend(self) -> List[Tuple[float, float]]:
        """计算评分趋势（保持原有逻辑）"""
        with QMutexLocker(self.evaluation_lock):
            # 至少需要3个数据点才能计算趋势
            if len(self.recent_evaluations) < 3:
                return [(eval['timestamp'], eval['overall_score']) 
                       for eval in self.recent_evaluations]
            
            # 提取最近10个数据点
            recent_data = self.recent_evaluations[-10:]
            return [(eval['timestamp'], eval['overall_score']) for eval in recent_data]

    def get_current_evaluation(self) -> Optional[Dict[str, Any]]:
        """获取当前评估结果（线程安全）"""
        with QMutexLocker(self.evaluation_lock):
            if self.recent_evaluations:
                return self.recent_evaluations[-1].copy()
            return None

    def reset_evaluation(self) -> None:
        """重置评估数据（线程安全）"""
        with QMutexLocker(self.evaluation_lock):
            self.recent_evaluations.clear()
            for key in self.behavior_counts:
                self.behavior_counts[key] = 0
            self.logger.info("驾驶行为评估数据已重置")

    def get_behavior_summary(self) -> Dict[str, int]:
        """获取行为统计摘要（线程安全）"""
        with QMutexLocker(self.evaluation_lock):
            return self.behavior_counts.copy()
    