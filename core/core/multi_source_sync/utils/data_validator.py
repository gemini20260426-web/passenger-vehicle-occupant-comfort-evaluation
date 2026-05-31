#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据验证器模块
提供数据完整性、格式和一致性验证功能

主要功能：
- 数据完整性验证
- 数据格式验证
- 数据一致性检查
- 验证规则配置
- 验证结果报告

版本: 1.0
创建时间: 2025年8月16日
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """验证级别"""
    CRITICAL = "critical"      # 关键验证失败
    WARNING = "warning"        # 警告级别
    INFO = "info"             # 信息级别


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool                    # 是否通过验证
    level: ValidationLevel            # 验证级别
    message: str                      # 验证消息
    details: Dict[str, Any]          # 详细验证信息
    timestamp: float                  # 验证时间戳
    source_id: Optional[str] = None  # 数据源ID


class DataValidator:
    """数据验证器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化数据验证器
        
        Args:
            config: 验证配置
        """
        self.config = config or {}
        self.validation_rules = self._load_validation_rules()
        self.validation_history = []
        
        logger.info("数据验证器初始化完成")
    
    def _load_validation_rules(self) -> Dict[str, Any]:
        """加载验证规则"""
        default_rules = {
            "required_fields": ["timestamp", "data"],
            "timestamp_format": "unix_timestamp",
            "data_type_checks": True,
            "range_validation": True,
            "consistency_checks": True
        }
        
        # 合并用户配置
        if self.config and "validation_rules" in self.config:
            default_rules.update(self.config["validation_rules"])
        
        return default_rules
    
    def validate_data_source(self, source_id: str, data: Dict[str, Any]) -> ValidationResult:
        """
        验证数据源数据
        
        Args:
            source_id: 数据源ID
            data: 待验证的数据
            
        Returns:
            ValidationResult: 验证结果
        """
        start_time = time.time()
        
        try:
            # 1. 基础验证
            basic_validation = self._validate_basic_structure(data)
            if not basic_validation.is_valid:
                return self._create_validation_result(
                    False, ValidationLevel.CRITICAL,
                    f"基础结构验证失败: {basic_validation.message}",
                    basic_validation.details,
                    start_time,
                    source_id
                )
            
            # 2. 字段完整性验证
            completeness_validation = self._validate_field_completeness(data)
            if not completeness_validation.is_valid:
                return self._create_validation_result(
                    False, ValidationLevel.CRITICAL,
                    f"字段完整性验证失败: {completeness_validation.message}",
                    completeness_validation.details,
                    start_time,
                    source_id
                )
            
            # 3. 数据类型验证
            type_validation = self._validate_data_types(data)
            if not type_validation.is_valid:
                return self._create_validation_result(
                    False, ValidationLevel.WARNING,
                    f"数据类型验证失败: {type_validation.message}",
                    type_validation.details,
                    start_time,
                    source_id
                )
            
            # 4. 数据范围验证
            range_validation = self._validate_data_ranges(data)
            if not range_validation.is_valid:
                return self._create_validation_result(
                    False, ValidationLevel.WARNING,
                    f"数据范围验证失败: {range_validation.message}",
                    range_validation.details,
                    start_time,
                    source_id
                )
            
            # 5. 数据一致性验证
            consistency_validation = self._validate_data_consistency(data)
            if not consistency_validation.is_valid:
                return self._create_validation_result(
                    False, ValidationLevel.WARNING,
                    f"数据一致性验证失败: {consistency_validation.message}",
                    consistency_validation.details,
                    start_time,
                    source_id
                )
            
            # 所有验证通过
            validation_result = self._create_validation_result(
                True, ValidationLevel.INFO,
                "数据验证通过",
                {
                    "validation_time": time.time() - start_time,
                    "total_checks": 5,
                    "passed_checks": 5
                },
                start_time,
                source_id
            )
            
            # 记录验证历史
            self.validation_history.append(validation_result)
            
            return validation_result
            
        except Exception as e:
            logger.error(f"数据验证过程中发生错误: {e}")
            return self._create_validation_result(
                False, ValidationLevel.CRITICAL,
                f"验证过程异常: {str(e)}",
                {"error": str(e)},
                start_time,
                source_id
            )
    
    def _validate_basic_structure(self, data: Dict[str, Any]) -> ValidationResult:
        """验证基础数据结构"""
        try:
            if not isinstance(data, dict):
                return ValidationResult(
                    False, ValidationLevel.CRITICAL,
                    "数据必须是字典类型",
                    {"expected_type": "dict", "actual_type": type(data).__name__},
                    time.time()
                )
            
            if not data:
                return ValidationResult(
                    False, ValidationLevel.CRITICAL,
                    "数据不能为空",
                    {"data_size": 0},
                    time.time()
                )
            
            return ValidationResult(
                True, ValidationLevel.INFO,
                "基础结构验证通过",
                {"data_type": "dict", "data_size": len(data)},
                time.time()
            )
            
        except Exception as e:
            return ValidationResult(
                False, ValidationLevel.CRITICAL,
                f"基础结构验证异常: {str(e)}",
                {"error": str(e)},
                time.time()
            )
    
    def _validate_field_completeness(self, data: Dict[str, Any]) -> ValidationResult:
        """验证字段完整性"""
        try:
            required_fields = self.validation_rules.get("required_fields", [])
            missing_fields = []
            
            for field in required_fields:
                if field not in data:
                    missing_fields.append(field)
            
            if missing_fields:
                return ValidationResult(
                    False, ValidationLevel.CRITICAL,
                    f"缺少必需字段: {', '.join(missing_fields)}",
                    {"missing_fields": missing_fields, "required_fields": required_fields},
                    time.time()
                )
            
            return ValidationResult(
                True, ValidationLevel.INFO,
                "字段完整性验证通过",
                {"required_fields": required_fields, "available_fields": list(data.keys())},
                time.time()
            )
            
        except Exception as e:
            return ValidationResult(
                False, ValidationLevel.CRITICAL,
                f"字段完整性验证异常: {str(e)}",
                {"error": str(e)},
                time.time()
            )
    
    def _validate_data_types(self, data: Dict[str, Any]) -> ValidationResult:
        """验证数据类型"""
        try:
            if not self.validation_rules.get("data_type_checks", True):
                return ValidationResult(
                    True, ValidationLevel.INFO,
                    "数据类型验证已禁用",
                    {"type_checks_enabled": False},
                    time.time()
                )
            
            type_issues = []
            
            # 检查时间戳字段
            if "timestamp" in data:
                if not isinstance(data["timestamp"], (int, float)):
                    type_issues.append({
                        "field": "timestamp",
                        "expected_type": "int/float",
                        "actual_type": type(data["timestamp"]).__name__
                    })
            
            # 检查数据字段
            if "data" in data:
                if not isinstance(data["data"], (dict, list, int, float, str)):
                    type_issues.append({
                        "field": "data",
                        "expected_type": "dict/list/int/float/str",
                        "actual_type": type(data["data"]).__name__
                    })
            
            if type_issues:
                return ValidationResult(
                    False, ValidationLevel.WARNING,
                    f"数据类型验证失败: {len(type_issues)} 个问题",
                    {"type_issues": type_issues},
                    time.time()
                )
            
            return ValidationResult(
                True, ValidationLevel.INFO,
                "数据类型验证通过",
                {"type_checks": "enabled", "issues_found": 0},
                time.time()
            )
            
        except Exception as e:
            return ValidationResult(
                False, ValidationLevel.CRITICAL,
                f"数据类型验证异常: {str(e)}",
                {"error": str(e)},
                time.time()
            )
    
    def _validate_data_ranges(self, data: Dict[str, Any]) -> ValidationResult:
        """验证数据范围"""
        try:
            if not self.validation_rules.get("range_validation", True):
                return ValidationResult(
                    True, ValidationLevel.INFO,
                    "数据范围验证已禁用",
                    {"range_validation_enabled": False},
                    time.time()
                )
            
            range_issues = []
            
            # 检查时间戳范围
            if "timestamp" in data:
                timestamp = data["timestamp"]
                if isinstance(timestamp, (int, float)):
                    current_time = time.time()
                    # 时间戳不能太旧（超过1年）或太新（超过1小时）
                    if timestamp < current_time - 365 * 24 * 3600:
                        range_issues.append({
                            "field": "timestamp",
                            "issue": "时间戳过旧",
                            "value": timestamp,
                            "threshold": current_time - 365 * 24 * 3600
                        })
                    elif timestamp > current_time + 3600:
                        range_issues.append({
                            "field": "timestamp",
                            "issue": "时间戳过新",
                            "value": timestamp,
                            "threshold": current_time + 3600
                        })
            
            if range_issues:
                return ValidationResult(
                    False, ValidationLevel.WARNING,
                    f"数据范围验证失败: {len(range_issues)} 个问题",
                    {"range_issues": range_issues},
                    time.time()
                )
            
            return ValidationResult(
                True, ValidationLevel.INFO,
                "数据范围验证通过",
                {"range_validation": "enabled", "issues_found": 0},
                time.time()
            )
            
        except Exception as e:
            return ValidationResult(
                False, ValidationLevel.CRITICAL,
                f"数据范围验证异常: {str(e)}",
                {"error": str(e)},
                time.time()
            )
    
    def _validate_data_consistency(self, data: Dict[str, Any]) -> ValidationResult:
        """验证数据一致性"""
        try:
            if not self.validation_rules.get("consistency_checks", True):
                return ValidationResult(
                    True, ValidationLevel.INFO,
                    "数据一致性验证已禁用",
                    {"consistency_checks_enabled": False},
                    time.time()
                )
            
            consistency_issues = []
            
            # 检查数据内部一致性
            if "data" in data and isinstance(data["data"], dict):
                data_dict = data["data"]
                
                # 检查是否有空值
                for key, value in data_dict.items():
                    if value is None:
                        consistency_issues.append({
                            "field": f"data.{key}",
                            "issue": "空值",
                            "value": None
                        })
                
                # 检查数值字段的一致性
                numeric_fields = []
                for key, value in data_dict.items():
                    if isinstance(value, (int, float)):
                        numeric_fields.append((key, value))
                
                if len(numeric_fields) > 1:
                    # 检查数值是否在合理范围内
                    for key, value in numeric_fields:
                        if isinstance(value, (int, float)) and abs(value) > 1e6:
                            consistency_issues.append({
                                "field": f"data.{key}",
                                "issue": "数值过大",
                                "value": value,
                                "threshold": 1e6
                            })
            
            if consistency_issues:
                return ValidationResult(
                    False, ValidationLevel.WARNING,
                    f"数据一致性验证失败: {len(consistency_issues)} 个问题",
                    {"consistency_issues": consistency_issues},
                    time.time()
                )
            
            return ValidationResult(
                True, ValidationLevel.INFO,
                "数据一致性验证通过",
                {"consistency_checks": "enabled", "issues_found": 0},
                time.time()
            )
            
        except Exception as e:
            return ValidationResult(
                False, ValidationLevel.CRITICAL,
                f"数据一致性验证异常: {str(e)}",
                {"error": str(e)},
                time.time()
            )
    
    def _create_validation_result(self, is_valid: bool, level: ValidationLevel, 
                                 message: str, details: Dict[str, Any], 
                                 timestamp: float, source_id: Optional[str] = None) -> ValidationResult:
        """创建验证结果对象"""
        return ValidationResult(
            is_valid=is_valid,
            level=level,
            message=message,
            details=details,
            timestamp=timestamp,
            source_id=source_id
        )
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """获取验证摘要"""
        if not self.validation_history:
            return {"total_validations": 0, "success_rate": 0.0}
        
        total = len(self.validation_history)
        successful = sum(1 for result in self.validation_history if result.is_valid)
        success_rate = (successful / total) * 100
        
        # 按级别统计
        level_counts = {}
        for result in self.validation_history:
            level = result.level.value
            level_counts[level] = level_counts.get(level, 0) + 1
        
        return {
            "total_validations": total,
            "successful_validations": successful,
            "failed_validations": total - successful,
            "success_rate": round(success_rate, 2),
            "level_distribution": level_counts
        }
    
    def clear_validation_history(self):
        """清除验证历史"""
        self.validation_history.clear()
        logger.info("验证历史已清除")
    
    def export_validation_report(self) -> Dict[str, Any]:
        """导出验证报告"""
        summary = self.get_validation_summary()
        
        # 最近的验证结果
        recent_results = []
        for result in self.validation_history[-10:]:  # 最近10个结果
            recent_results.append({
                "source_id": result.source_id,
                "timestamp": result.timestamp,
                "is_valid": result.is_valid,
                "level": result.level.value,
                "message": result.message
            })
        
        return {
            "report_timestamp": time.time(),
            "summary": summary,
            "recent_results": recent_results,
            "validation_rules": self.validation_rules
        }
