#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据质量评估器模块
提供数据质量评估、评分和监控功能

主要功能：
- 数据完整性评估
- 数据准确性评估
- 数据一致性评估
- 数据时效性评估
- 综合质量评分
- 质量趋势分析

版本: 1.0
创建时间: 2025年8月16日
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class QualityDimension(Enum):
    """质量维度"""
    COMPLETENESS = "completeness"    # 完整性
    ACCURACY = "accuracy"            # 准确性
    CONSISTENCY = "consistency"      # 一致性
    TIMELINESS = "timeliness"        # 时效性
    VALIDITY = "validity"            # 有效性


@dataclass
class QualityScore:
    """质量评分"""
    dimension: QualityDimension      # 质量维度
    score: float                     # 评分 (0-100)
    weight: float                    # 权重
    details: Dict[str, Any]         # 详细评分信息
    timestamp: float                 # 评分时间戳


@dataclass
class OverallQualityScore:
    """综合质量评分"""
    overall_score: float             # 综合评分 (0-100)
    dimension_scores: List[QualityScore]  # 各维度评分
    timestamp: float                 # 评分时间戳
    source_id: str                   # 数据源ID


class DataQualityAssessor:
    """数据质量评估器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化数据质量评估器
        
        Args:
            config: 评估配置
        """
        self.config = config or {}
        self.quality_weights = self._load_quality_weights()
        self.quality_history = []
        self.assessment_rules = self._load_assessment_rules()
        
        logger.info("数据质量评估器初始化完成")
    
    def _load_quality_weights(self) -> Dict[QualityDimension, float]:
        """加载质量权重配置"""
        default_weights = {
            QualityDimension.COMPLETENESS: 0.25,
            QualityDimension.ACCURACY: 0.30,
            QualityDimension.CONSISTENCY: 0.20,
            QualityDimension.TIMELINESS: 0.15,
            QualityDimension.VALIDITY: 0.10
        }
        
        # 合并用户配置
        if self.config and "quality_weights" in self.config:
            user_weights = self.config["quality_weights"]
            for dim_name, weight in user_weights.items():
                try:
                    dim = QualityDimension(dim_name)
                    default_weights[dim] = weight
                except ValueError:
                    logger.warning(f"未知的质量维度: {dim_name}")
        
        return default_weights
    
    def _load_assessment_rules(self) -> Dict[str, Any]:
        """加载评估规则"""
        default_rules = {
            "completeness_threshold": 0.8,      # 完整性阈值
            "accuracy_threshold": 0.85,         # 准确性阈值
            "consistency_threshold": 0.75,      # 一致性阈值
            "timeliness_threshold": 0.9,        # 时效性阈值
            "validity_threshold": 0.8,          # 有效性阈值
            "overall_threshold": 0.8            # 综合阈值
        }
        
        # 合并用户配置
        if self.config and "assessment_rules" in self.config:
            default_rules.update(self.config["assessment_rules"])
        
        return default_rules
    
    def assess_data_quality(self, source_id: str, data: Dict[str, Any]) -> OverallQualityScore:
        """
        评估数据质量
        
        Args:
            source_id: 数据源ID
            data: 待评估的数据
            
        Returns:
            OverallQualityScore: 综合质量评分
        """
        start_time = time.time()
        
        try:
            # 1. 完整性评估
            completeness_score = self._assess_completeness(data)
            
            # 2. 准确性评估
            accuracy_score = self._assess_accuracy(data)
            
            # 3. 一致性评估
            consistency_score = self._assess_consistency(data)
            
            # 4. 时效性评估
            timeliness_score = self._assess_timeliness(data)
            
            # 5. 有效性评估
            validity_score = self._assess_validity(data)
            
            # 6. 计算综合评分
            dimension_scores = [
                completeness_score,
                accuracy_score,
                consistency_score,
                timeliness_score,
                validity_score
            ]
            
            overall_score = self._calculate_overall_score(dimension_scores)
            
            # 7. 创建综合评分对象
            overall_quality = OverallQualityScore(
                overall_score=overall_score,
                dimension_scores=dimension_scores,
                timestamp=start_time,
                source_id=source_id
            )
            
            # 8. 记录评估历史
            self.quality_history.append(overall_quality)
            
            logger.info(f"数据源 {source_id} 质量评估完成，综合评分: {overall_score:.2f}")
            
            return overall_quality
            
        except Exception as e:
            logger.error(f"数据质量评估过程中发生错误: {e}")
            # 返回最低评分
            return OverallQualityScore(
                overall_score=0.0,
                dimension_scores=[],
                timestamp=start_time,
                source_id=source_id
            )
    
    def _assess_completeness(self, data: Dict[str, Any]) -> QualityScore:
        """评估数据完整性"""
        try:
            required_fields = self.config.get("required_fields", ["timestamp", "data"])
            available_fields = list(data.keys())
            
            # 计算字段完整性
            missing_fields = [field for field in required_fields if field not in available_fields]
            completeness_ratio = 1.0 - (len(missing_fields) / len(required_fields))
            
            # 计算数据值完整性
            non_null_count = 0
            total_fields = len(available_fields)
            
            for field, value in data.items():
                if value is not None and value != "":
                    non_null_count += 1
            
            value_completeness = non_null_count / total_fields if total_fields > 0 else 0.0
            
            # 综合完整性评分
            final_score = (completeness_ratio * 0.7 + value_completeness * 0.3) * 100
            
            return QualityScore(
                dimension=QualityDimension.COMPLETENESS,
                score=min(final_score, 100.0),
                weight=self.quality_weights[QualityDimension.COMPLETENESS],
                details={
                    "required_fields": required_fields,
                    "missing_fields": missing_fields,
                    "completeness_ratio": completeness_ratio,
                    "value_completeness": value_completeness
                },
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"完整性评估失败: {e}")
            return QualityScore(
                dimension=QualityDimension.COMPLETENESS,
                score=0.0,
                weight=self.quality_weights[QualityDimension.COMPLETENESS],
                details={"error": str(e)},
                timestamp=time.time()
            )
    
    def _assess_accuracy(self, data: Dict[str, Any]) -> QualityScore:
        """评估数据准确性"""
        try:
            accuracy_score = 100.0
            accuracy_issues = []
            
            # 检查时间戳准确性
            if "timestamp" in data:
                timestamp = data["timestamp"]
                current_time = time.time()
                
                if isinstance(timestamp, (int, float)):
                    time_diff = abs(current_time - timestamp)
                    
                    if time_diff > 3600:  # 超过1小时
                        accuracy_score -= 20
                        accuracy_issues.append({
                            "field": "timestamp",
                            "issue": "时间戳偏差过大",
                            "deviation": time_diff
                        })
                    elif time_diff > 300:  # 超过5分钟
                        accuracy_score -= 10
                        accuracy_issues.append({
                            "field": "timestamp",
                            "issue": "时间戳偏差较大",
                            "deviation": time_diff
                        })
            
            # 检查数值字段的合理性
            if "data" in data and isinstance(data["data"], dict):
                data_dict = data["data"]
                
                for key, value in data_dict.items():
                    if isinstance(value, (int, float)):
                        # 检查异常值
                        if abs(value) > 1e6:
                            accuracy_score -= 15
                            accuracy_issues.append({
                                "field": f"data.{key}",
                                "issue": "数值异常",
                                "value": value
                            })
                        elif value == 0 and key.lower() in ["speed", "acceleration", "temperature"]:
                            # 某些字段不应该为0
                            accuracy_score -= 10
                            accuracy_issues.append({
                                "field": f"data.{key}",
                                "issue": "可疑的零值",
                                "value": value
                            })
            
            return QualityScore(
                dimension=QualityDimension.ACCURACY,
                score=max(accuracy_score, 0.0),
                weight=self.quality_weights[QualityDimension.ACCURACY],
                details={
                    "accuracy_issues": accuracy_issues,
                    "issues_count": len(accuracy_issues)
                },
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"准确性评估失败: {e}")
            return QualityScore(
                dimension=QualityDimension.ACCURACY,
                score=0.0,
                weight=self.quality_weights[QualityDimension.ACCURACY],
                details={"error": str(e)},
                timestamp=time.time()
            )
    
    def _assess_consistency(self, data: Dict[str, Any]) -> QualityScore:
        """评估数据一致性"""
        try:
            consistency_score = 100.0
            consistency_issues = []
            
            if "data" in data and isinstance(data["data"], dict):
                data_dict = data["data"]
                
                # 检查数值字段的一致性
                numeric_fields = {}
                for key, value in data_dict.items():
                    if isinstance(value, (int, float)):
                        numeric_fields[key] = value
                
                if len(numeric_fields) > 1:
                    # 检查数值范围的一致性
                    values = list(numeric_fields.values())
                    value_range = max(values) - min(values)
                    mean_value = sum(values) / len(values)
                    
                    if mean_value != 0:
                        coefficient_of_variation = value_range / abs(mean_value)
                        
                        if coefficient_of_variation > 10:  # 变异系数过大
                            consistency_score -= 25
                            consistency_issues.append({
                                "issue": "数值变异系数过大",
                                "coefficient": coefficient_of_variation,
                                "fields": list(numeric_fields.keys())
                            })
                        elif coefficient_of_variation > 5:
                            consistency_score -= 15
                            consistency_issues.append({
                                "issue": "数值变异系数较大",
                                "coefficient": coefficient_of_variation,
                                "fields": list(numeric_fields.keys())
                            })
                
                # 检查字段命名的一致性
                field_names = list(data_dict.keys())
                naming_patterns = {}
                
                for field_name in field_names:
                    # 简单的命名模式检查
                    if "_" in field_name:
                        naming_patterns["underscore"] = naming_patterns.get("underscore", 0) + 1
                    elif field_name[0].isupper():
                        naming_patterns["camelcase"] = naming_patterns.get("camelcase", 0) + 1
                    else:
                        naming_patterns["lowercase"] = naming_patterns.get("lowercase", 0) + 1
                
                # 如果命名模式不统一，扣分
                if len(naming_patterns) > 1:
                    dominant_pattern = max(naming_patterns, key=naming_patterns.get)
                    pattern_consistency = naming_patterns[dominant_pattern] / len(field_names)
                    
                    if pattern_consistency < 0.8:
                        consistency_score -= 10
                        consistency_issues.append({
                            "issue": "字段命名模式不统一",
                            "patterns": naming_patterns,
                            "dominant_pattern": dominant_pattern
                        })
            
            return QualityScore(
                dimension=QualityDimension.CONSISTENCY,
                score=max(consistency_score, 0.0),
                weight=self.quality_weights[QualityDimension.CONSISTENCY],
                details={
                    "consistency_issues": consistency_issues,
                    "issues_count": len(consistency_issues)
                },
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"一致性评估失败: {e}")
            return QualityScore(
                dimension=QualityDimension.CONSISTENCY,
                score=0.0,
                weight=self.quality_weights[QualityDimension.CONSISTENCY],
                details={"error": str(e)},
                timestamp=time.time()
            )
    
    def _assess_timeliness(self, data: Dict[str, Any]) -> QualityScore:
        """评估数据时效性"""
        try:
            timeliness_score = 100.0
            timeliness_issues = []
            
            if "timestamp" in data:
                timestamp = data["timestamp"]
                current_time = time.time()
                
                if isinstance(timestamp, (int, float)):
                    time_diff = current_time - timestamp
                    
                    if time_diff > 300:  # 超过5分钟
                        timeliness_score -= 50
                        timeliness_issues.append({
                            "issue": "数据延迟严重",
                            "delay_seconds": time_diff
                        })
                    elif time_diff > 60:  # 超过1分钟
                        timeliness_score -= 30
                        timeliness_issues.append({
                            "issue": "数据延迟较大",
                            "delay_seconds": time_diff
                        })
                    elif time_diff > 10:  # 超过10秒
                        timeliness_score -= 15
                        timeliness_issues.append({
                            "issue": "数据轻微延迟",
                            "delay_seconds": time_diff
                        })
                    
                    # 检查数据是否来自未来
                    if timestamp > current_time:
                        timeliness_score -= 30
                        timeliness_issues.append({
                            "issue": "数据时间戳来自未来",
                            "future_offset": timestamp - current_time
                        })
            
            return QualityScore(
                dimension=QualityDimension.TIMELINESS,
                score=max(timeliness_score, 0.0),
                weight=self.quality_weights[QualityDimension.TIMELINESS],
                details={
                    "timeliness_issues": timeliness_issues,
                    "issues_count": len(timeliness_issues)
                },
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"时效性评估失败: {e}")
            return QualityScore(
                dimension=QualityDimension.TIMELINESS,
                score=0.0,
                weight=self.quality_weights[QualityDimension.TIMELINESS],
                details={"error": str(e)},
                timestamp=time.time()
            )
    
    def _assess_validity(self, data: Dict[str, Any]) -> QualityScore:
        """评估数据有效性"""
        try:
            validity_score = 100.0
            validity_issues = []
            
            # 检查数据格式有效性
            if not isinstance(data, dict):
                validity_score -= 100
                validity_issues.append({
                    "issue": "数据格式无效",
                    "expected": "dict",
                    "actual": type(data).__name__
                })
            else:
                # 检查必需字段
                required_fields = self.config.get("required_fields", ["timestamp", "data"])
                for field in required_fields:
                    if field not in data:
                        validity_score -= 20
                        validity_issues.append({
                            "issue": "缺少必需字段",
                            "field": field
                        })
                
                # 检查字段值类型
                if "timestamp" in data:
                    if not isinstance(data["timestamp"], (int, float)):
                        validity_score -= 15
                        validity_issues.append({
                            "issue": "时间戳字段类型无效",
                            "field": "timestamp",
                            "expected": "int/float",
                            "actual": type(data["timestamp"]).__name__
                        })
                
                if "data" in data:
                    if not isinstance(data["data"], (dict, list, int, float, str)):
                        validity_score -= 15
                        validity_issues.append({
                            "issue": "数据字段类型无效",
                            "field": "data",
                            "expected": "dict/list/int/float/str",
                            "actual": type(data["data"]).__name__
                        })
            
            return QualityScore(
                dimension=QualityDimension.VALIDITY,
                score=max(validity_score, 0.0),
                weight=self.quality_weights[QualityDimension.VALIDITY],
                details={
                    "validity_issues": validity_issues,
                    "issues_count": len(validity_issues)
                },
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"有效性评估失败: {e}")
            return QualityScore(
                dimension=QualityDimension.VALIDITY,
                score=0.0,
                weight=self.quality_weights[QualityDimension.VALIDITY],
                details={"error": str(e)},
                timestamp=time.time()
            )
    
    def _calculate_overall_score(self, dimension_scores: List[QualityScore]) -> float:
        """计算综合质量评分"""
        try:
            if not dimension_scores:
                return 0.0
            
            weighted_sum = 0.0
            total_weight = 0.0
            
            for score in dimension_scores:
                weighted_sum += score.score * score.weight
                total_weight += score.weight
            
            if total_weight == 0:
                return 0.0
            
            overall_score = weighted_sum / total_weight
            
            return min(overall_score, 100.0)
            
        except Exception as e:
            logger.error(f"综合评分计算失败: {e}")
            return 0.0
    
    def get_quality_summary(self) -> Dict[str, Any]:
        """获取质量评估摘要"""
        if not self.quality_history:
            return {"total_assessments": 0, "average_score": 0.0}
        
        total = len(self.quality_history)
        total_score = sum(assessment.overall_score for assessment in self.quality_history)
        average_score = total_score / total
        
        # 按评分等级统计
        score_ranges = {
            "excellent": 0,    # 90-100
            "good": 0,         # 80-89
            "fair": 0,         # 70-79
            "poor": 0,         # 60-69
            "very_poor": 0     # 0-59
        }
        
        for assessment in self.quality_history:
            score = assessment.overall_score
            if score >= 90:
                score_ranges["excellent"] += 1
            elif score >= 80:
                score_ranges["good"] += 1
            elif score >= 70:
                score_ranges["fair"] += 1
            elif score >= 60:
                score_ranges["poor"] += 1
            else:
                score_ranges["very_poor"] += 1
        
        return {
            "total_assessments": total,
            "average_score": round(average_score, 2),
            "score_distribution": score_ranges
        }
    
    def clear_quality_history(self):
        """清除质量评估历史"""
        self.quality_history.clear()
        logger.info("质量评估历史已清除")
    
    def export_quality_report(self) -> Dict[str, Any]:
        """导出质量评估报告"""
        summary = self.get_quality_summary()
        
        # 最近的评估结果
        recent_assessments = []
        for assessment in self.quality_history[-10:]:  # 最近10个评估
            recent_assessments.append({
                "source_id": assessment.source_id,
                "timestamp": assessment.timestamp,
                "overall_score": assessment.overall_score,
                "dimension_scores": [
                    {
                        "dimension": score.dimension.value,
                        "score": score.score,
                        "weight": score.weight
                    }
                    for score in assessment.dimension_scores
                ]
            })
        
        return {
            "report_timestamp": time.time(),
            "summary": summary,
            "recent_assessments": recent_assessments,
            "quality_weights": {dim.value: weight for dim, weight in self.quality_weights.items()},
            "assessment_rules": self.assessment_rules
        }
