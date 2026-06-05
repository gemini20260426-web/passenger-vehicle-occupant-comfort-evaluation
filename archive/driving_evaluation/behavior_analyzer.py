"""驾驶行为分析模块（检测急加速、急刹车等行为）"""
import time
import logging
from typing import Dict, List, Any, Optional
import numpy as np
from PySide6.QtCore import QObject, Signal, QMutex, QMutexLocker
from Driveranalysis.utils.ConfigManager import ConfigManager

config_manager = ConfigManager()
behavior_thresholds = config_manager.get_config('driving_behavior_thresholds')
from common.exceptions import BehaviorAnalysisError

class BehaviorAnalyzer(QObject):
    """驾驶行为分析器（保持原有类名和核心逻辑）"""
    # 新增信号机制，用于线程安全通信
    behavior_detected = Signal(dict)  # 检测到行为事件时发射
    analysis_error = Signal(str)      # 分析错误时发射
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # 线程安全锁（新增）
        self.analysis_lock = QMutex()
        
        # 配置参数（保持原有命名）
        self.hard_accel_threshold = config.get('hard_accel_threshold', HARD_ACCEL_THRESHOLD)
        self.hard_brake_threshold = config.get('hard_brake_threshold', HARD_BRAKE_THRESHOLD)
        self.sharp_turn_threshold = config.get('sharp_turn_threshold', SHARP_TURN_THRESHOLD)
        self.overspeed_threshold = config.get('overspeed_threshold', behavior_thresholds['overspeed_threshold'])
        
        # 历史数据缓存（用于趋势分析，保持原有命名）
        self.accel_history = []
        self.turn_history = []
        self.speed_history = []
        self.history_window = 5  # 分析窗口大小
        
        # 行为冷却机制（防止重复触发，新增）
        self.behavior_cooldowns = {
            'hard_acceleration': 0,
            'hard_braking': 0,
            'sharp_turning': 0,
            'overspeeding': 0
        }
        self.cooldown_period = 2.0  # 2秒冷却时间

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """更新分析配置参数（保持原有方法）"""
        with QMutexLocker(self.analysis_lock):  # 新增线程安全保护
            if 'hard_accel_threshold' in new_config:
                self.hard_accel_threshold = new_config['hard_accel_threshold']
            if 'hard_brake_threshold' in new_config:
                self.hard_brake_threshold = new_config['hard_brake_threshold']
            if 'sharp_turn_threshold' in new_config:
                self.sharp_turn_threshold = new_config['sharp_turn_threshold']
            if 'overspeed_threshold' in new_config:
                self.overspeed_threshold = new_config['overspeed_threshold']
            self.logger.info("行为分析配置已更新")

    def analyze_data(self, data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """分析单条驾驶数据（保持原有方法名）"""
        if not data:
            return None
            
        try:
            with QMutexLocker(self.analysis_lock):  # 新增线程安全保护
                # 验证必要字段（增强版，原有基础上扩展）
                required_fields = ['timestamp', 'speed', 
                                  'acceleration_x', 'acceleration_y', 'acceleration_z',
                                  'angular_velocity_x', 'angular_velocity_y', 'angular_velocity_z']
                for field in required_fields:
                    if field not in data:
                        raise BehaviorAnalysisError(f"数据缺少必要字段: {field}")

                # 存储历史数据（保持原有逻辑）
                self._update_history(data)
                
                # 检测各类驾驶行为（保持原有方法调用）
                behaviors = []
                current_time = time.time()
                
                # 急加速检测
                accel_behavior = self._detect_hard_acceleration(data, current_time)
                if accel_behavior:
                    behaviors.append(accel_behavior)
                
                # 急刹车检测
                brake_behavior = self._detect_hard_braking(data, current_time)
                if brake_behavior:
                    behaviors.append(brake_behavior)
                
                # 急转弯检测
                turn_behavior = self._detect_sharp_turn(data, current_time)
                if turn_behavior:
                    behaviors.append(turn_behavior)
                
                # 超速检测
                speed_behavior = self._detect_overspeeding(data, current_time)
                if speed_behavior:
                    behaviors.append(speed_behavior)
                
                # 发射信号通知检测结果（新增）
                for behavior in behaviors:
                    self.behavior_detected.emit(behavior)
                    
                return behaviors
                
        except Exception as e:
            error_msg = f"行为分析失败: {str(e)}"
            self.logger.error(error_msg)
            self.analysis_error.emit(error_msg)
            return None

    def _update_history(self, data: Dict[str, Any]) -> None:
        """更新历史数据缓存（保持原有方法）"""
        # 加速度历史
        self.accel_history.append([
            data['acceleration_x'], 
            data['acceleration_y'], 
            data['acceleration_z']
        ])
        # 角速度历史（转弯分析用）
        self.turn_history.append([
            data['angular_velocity_x'], 
            data['angular_velocity_y'], 
            data['angular_velocity_z']
        ])
        # 速度历史
        self.speed_history.append(data['speed'])
        
        # 保持窗口大小（原有逻辑）
        if len(self.accel_history) > self.history_window:
            self.accel_history.pop(0)
        if len(self.turn_history) > self.history_window:
            self.turn_history.pop(0)
        if len(self.speed_history) > self.history_window:
            self.speed_history.pop(0)

    def _detect_hard_acceleration(self, data: Dict[str, Any], current_time: float) -> Optional[Dict[str, Any]]:
        """检测急加速行为（保持原有方法）"""
        # 检查冷却时间（新增）
        if current_time < self.behavior_cooldowns['hard_acceleration']:
            return None
            
        # 计算加速度大小（原有逻辑）
        accel_magnitude = np.sqrt(
            data['acceleration_x']**2 + 
            data['acceleration_y']** 2 + 
            data['acceleration_z']**2
        )
        
        # 判断是否超过阈值（原有逻辑）
        if accel_magnitude > self.hard_accel_threshold:
            self.behavior_cooldowns['hard_acceleration'] = current_time + self.cooldown_period
            return {
                'timestamp': data['timestamp'],
                'event_type': 'hard_acceleration',
                'severity': self._calculate_severity(accel_magnitude, self.hard_accel_threshold),
                'speed': data['speed'],
                'value': round(accel_magnitude, 2),
                'threshold': self.hard_accel_threshold,
                'location': {
                    'latitude': data.get('latitude'),
                    'longitude': data.get('longitude')
                }
            }
        return None

    def _detect_hard_braking(self, data: Dict[str, Any], current_time: float) -> Optional[Dict[str, Any]]:
        """检测急刹车行为（保持原有方法）"""
        if current_time < self.behavior_cooldowns['hard_braking']:
            return None
            
        # 急刹车主要看负向加速度（原有逻辑）
        brake_force = abs(data['acceleration_x'])  # 假设x轴为前进方向
        
        if brake_force > self.hard_brake_threshold:
            self.behavior_cooldowns['hard_braking'] = current_time + self.cooldown_period
            return {
                'timestamp': data['timestamp'],
                'event_type': 'hard_braking',
                'severity': self._calculate_severity(brake_force, self.hard_brake_threshold),
                'speed': data['speed'],
                'value': round(brake_force, 2),
                'threshold': self.hard_brake_threshold,
                'location': {
                    'latitude': data.get('latitude'),
                    'longitude': data.get('longitude')
                }
            }
        return None

    def _detect_sharp_turn(self, data: Dict[str, Any], current_time: float) -> Optional[Dict[str, Any]]:
        """检测急转弯行为（保持原有方法）"""
        if current_time < self.behavior_cooldowns['sharp_turning']:
            return None
            
        # 计算角速度大小（原有逻辑）
        turn_magnitude = np.sqrt(
            data['angular_velocity_x']**2 + 
            data['angular_velocity_y']** 2 + 
            data['angular_velocity_z']**2
        )
        
        if turn_magnitude > self.sharp_turn_threshold:
            self.behavior_cooldowns['sharp_turning'] = current_time + self.cooldown_period
            return {
                'timestamp': data['timestamp'],
                'event_type': 'sharp_turning',
                'severity': self._calculate_severity(turn_magnitude, self.sharp_turn_threshold),
                'speed': data['speed'],
                'value': round(turn_magnitude, 2),
                'threshold': self.sharp_turn_threshold,
                'location': {
                    'latitude': data.get('latitude'),
                    'longitude': data.get('longitude')
                }
            }
        return None

    def _detect_overspeeding(self, data: Dict[str, Any], current_time: float) -> Optional[Dict[str, Any]]:
        """检测超速行为（保持原有方法）"""
        # 超速冷却时间更长（30秒）
        if current_time < self.behavior_cooldowns['overspeeding']:
            return None
            
        if data['speed'] > self.overspeed_threshold:
            self.behavior_cooldowns['overspeeding'] = current_time + 30.0  # 30秒冷却
            return {
                'timestamp': data['timestamp'],
                'event_type': 'overspeeding',
                'severity': self._calculate_severity(data['speed'], self.overspeed_threshold),
                'speed': data['speed'],
                'value': round(data['speed'], 2),
                'threshold': self.overspeed_threshold,
                'location': {
                    'latitude': data.get('latitude'),
                    'longitude': data.get('longitude')
                }
            }
        return None

    def _calculate_severity(self, value: float, threshold: float) -> int:
        """计算行为严重程度（1-5级，保持原有方法）"""
        ratio = value / threshold
        if ratio < 1.2:
            return 1
        elif ratio < 1.5:
            return 2
        elif ratio < 2.0:
            return 3
        elif ratio < 3.0:
            return 4
        else:
            return 5

    def get_behavior_summary(self, period: int = 300) -> Dict[str, Any]:
        """获取行为统计摘要（保持原有方法）"""
        # 实际实现应从数据库查询，此处保持原有逻辑框架
        with QMutexLocker(self.analysis_lock):
            return {
                'period': period,
                'hard_acceleration_count': 0,
                'hard_braking_count': 0,
                'sharp_turning_count': 0,
                'overspeeding_count': 0,
                'severity_distribution': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            }
    