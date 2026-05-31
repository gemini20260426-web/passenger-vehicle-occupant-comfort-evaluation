#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能异常检测器模块
提供异常检测、分类和预警功能

版本: 1.0
创建时间: 2025年8月16日
"""

import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """异常类型"""
    DATA_QUALITY = "data_quality"
    PERFORMANCE = "performance"
    TIMING = "timing"
    SYSTEM = "system"


class AnomalySeverity(Enum):
    """异常严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AnomalyEvent:
    """异常事件"""
    anomaly_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    source_id: str
    message: str
    details: Dict[str, Any]
    timestamp: float
    confidence: float
    status: str = "active"


class IntelligentAnomalyDetector:
    """智能异常检测器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化异常检测器"""
        self.config = config or {}
        self.anomaly_history = []
        logger.info("智能异常检测器初始化完成")
    
    def detect_anomaly(self, source_id: str, data: Dict[str, Any]) -> Optional[AnomalyEvent]:
        """检测异常"""
        try:
            # 简单的异常检测逻辑
            if "quality_score" in data and data["quality_score"] < 0.8:
                return self._create_anomaly_event(
                    AnomalyType.DATA_QUALITY,
                    AnomalySeverity.MEDIUM,
                    source_id,
                    f"数据质量过低: {data['quality_score']}",
                    data
                )
            
            if "response_time" in data and data["response_time"] > 200:
                return self._create_anomaly_event(
                    AnomalyType.PERFORMANCE,
                    AnomalySeverity.HIGH,
                    source_id,
                    f"响应时间过长: {data['response_time']}ms",
                    data
                )
            
            return None
            
        except Exception as e:
            logger.error(f"异常检测失败: {e}")
            return None
    
    def _create_anomaly_event(self, anomaly_type: AnomalyType, severity: AnomalySeverity,
                             source_id: str, message: str, details: Dict[str, Any]) -> AnomalyEvent:
        """创建异常事件"""
        anomaly_id = f"{anomaly_type.value}_{source_id}_{int(time.time())}"
        
        event = AnomalyEvent(
            anomaly_id=anomaly_id,
            anomaly_type=anomaly_type,
            severity=severity,
            source_id=source_id,
            message=message,
            details=details,
            timestamp=time.time(),
            confidence=0.8
        )
        
        # 添加到历史记录
        self.anomaly_history.append(event)
        
        # 保持历史记录在合理范围内
        if len(self.anomaly_history) > 1000:
            self.anomaly_history = self.anomaly_history[-1000:]
        
        return event
    
    def detect_anomalies(self, data: Dict[str, Any]) -> List[AnomalyEvent]:
        """
        批量检测异常
        
        Args:
            data: 包含多个数据源数据的字典
            
        Returns:
            List[AnomalyEvent]: 检测到的异常事件列表
        """
        try:
            anomalies = []
            
            for source_id, source_data in data.items():
                if isinstance(source_data, dict):
                    anomaly = self.detect_anomaly(source_id, source_data)
                    if anomaly:
                        anomalies.append(anomaly)
            
            # 记录检测结果
            if anomalies:
                logger.info(f"检测到 {len(anomalies)} 个异常")
            else:
                logger.debug("未检测到异常")
            
            return anomalies
            
        except Exception as e:
            logger.error(f"批量异常检测失败: {e}")
            return []
    
    def get_anomaly_history(self, source_id: Optional[str] = None, 
                           anomaly_type: Optional[AnomalyType] = None,
                           severity: Optional[AnomalySeverity] = None,
                           limit: int = 100) -> List[AnomalyEvent]:
        """
        获取异常历史记录
        
        Args:
            source_id: 数据源ID（可选）
            anomaly_type: 异常类型（可选）
            severity: 异常严重程度（可选）
            limit: 返回记录数量限制
            
        Returns:
            List[AnomalyEvent]: 异常事件列表
        """
        try:
            filtered_anomalies = self.anomaly_history
            
            # 按数据源过滤
            if source_id:
                filtered_anomalies = [a for a in filtered_anomalies if a.source_id == source_id]
            
            # 按异常类型过滤
            if anomaly_type:
                filtered_anomalies = [a for a in filtered_anomalies if a.anomaly_type == anomaly_type]
            
            # 按严重程度过滤
            if severity:
                filtered_anomalies = [a for a in filtered_anomalies if a.severity == severity]
            
            # 按时间排序（最新的在前）
            filtered_anomalies.sort(key=lambda x: x.timestamp, reverse=True)
            
            # 限制返回数量
            return filtered_anomalies[:limit]
            
        except Exception as e:
            logger.error(f"获取异常历史记录失败: {e}")
            return []
    
    def clear_anomaly_history(self, source_id: Optional[str] = None) -> bool:
        """
        清除异常历史记录
        
        Args:
            source_id: 数据源ID（可选），如果为None则清除所有记录
            
        Returns:
            bool: 是否清除成功
        """
        try:
            if source_id:
                self.anomaly_history = [a for a in self.anomaly_history if a.source_id != source_id]
                logger.info(f"已清除数据源 {source_id} 的异常历史记录")
            else:
                self.anomaly_history.clear()
                logger.info("已清除所有异常历史记录")
            
            return True
            
        except Exception as e:
            logger.error(f"清除异常历史记录失败: {e}")
            return False
