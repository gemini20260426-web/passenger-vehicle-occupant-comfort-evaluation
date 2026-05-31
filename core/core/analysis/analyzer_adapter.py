#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
适配器模块：将base_analyzer.py的输出格式适配为analysis.py的输入格式
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np


class AnalyzerAdapter:
    """分析器适配器，用于连接基础分析器和高级分析器"""
    
    @staticmethod
    def adapt_base_result_for_advanced_analysis(base_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        将base_analyzer.py的输出适配为analysis.py的输入格式
        
        Args:
            base_result: base_analyzer.py的输出结果
            
        Returns:
            适配后的结果，可直接用于AdvancedBehaviorAnalyzer.analyze()
        """
        # base_analyzer.py输出格式:
        # {
        #     "timestamp": "时间戳",
        #     "window_start_time": "窗口开始时间",
        #     "window_end_time": "窗口结束时间",
        #     "behavior": "检测到的主要行为",
        #     "confidence": 0.9,  # 置信度
        #     "raw_data": {...},  # 原始数据
        #     "detected_all": [...]  # 所有检测到的行为
        # }
        
        # analysis.py期望的输入格式:
        # {
        #     "timestamp": "时间戳",
        #     "behavior": "基础行为",
        #     "confidence": 0.9,  # 置信度
        #     "raw_data": {...}   # 原始数据
        # }
        
        adapted_result = {
            "timestamp": base_result.get("timestamp", ""),
            "behavior": base_result.get("behavior", "normal"),
            "confidence": base_result.get("confidence", 0.85),
            "raw_data": base_result.get("raw_data", {})
        }
        
        return adapted_result
    
    @staticmethod
    def adapt_base_results_for_training(base_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将多个base_analyzer.py的输出结果适配为analysis.py训练所需的格式
        
        Args:
            base_results: base_analyzer.py的多个输出结果
            
        Returns:
            适配后的结果列表，可直接用于AdvancedBehaviorAnalyzer.train_model()
        """
        adapted_results = []
        for result in base_results:
            adapted_result = AnalyzerAdapter.adapt_base_result_for_advanced_analysis(result)
            adapted_results.append(adapted_result)
        return adapted_results
    
    @staticmethod
    def extract_features_from_base_result(base_result: Dict[str, Any],
                                          prev_result: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        从base_analyzer.py的输出中提取特征（11维标准特征集），用于机器学习模型训练

        Args:
            base_result: base_analyzer.py的输出结果
            prev_result: 上一条基础分析结果（用于计算speed_change_rate）

        Returns:
            包含特征的DataFrame
        """
        raw_data = base_result.get("raw_data", {})

        accel_mag = np.linalg.norm([
            raw_data.get("ax", 0),
            raw_data.get("ay", 0),
            raw_data.get("az", 0)
        ])

        turn_rate = np.linalg.norm([
            raw_data.get("gx", 0),
            raw_data.get("gy", 0),
            raw_data.get("gz", 0)
        ])

        speed_change_rate = 0.0
        if prev_result:
            try:
                prev_raw = prev_result.get("raw_data", {})
                curr_speed = raw_data.get("speed", 0)
                prev_speed = prev_raw.get("speed", 0)
                curr_ts = base_result.get("timestamp", 0)
                prev_ts = prev_result.get("timestamp", 0)
                if isinstance(curr_ts, str):
                    curr_ts = pd.to_datetime(curr_ts).timestamp()
                if isinstance(prev_ts, str):
                    prev_ts = pd.to_datetime(prev_ts).timestamp()
                time_diff = float(curr_ts) - float(prev_ts)
                if time_diff > 0:
                    speed_change_rate = (curr_speed - prev_speed) / time_diff
            except Exception:
                pass

        features = pd.DataFrame([{
            "speed": raw_data.get("speed", 0),
            "ax": raw_data.get("ax", 0),
            "ay": raw_data.get("ay", 0),
            "az": raw_data.get("az", 0),
            "gx": raw_data.get("gx", 0),
            "gy": raw_data.get("gy", 0),
            "gz": raw_data.get("gz", 0),
            "accel_magnitude": accel_mag,
            "turn_rate": turn_rate,
            "speed_change_rate": speed_change_rate,
            "behavior_confidence": base_result.get("confidence", 0)
        }])

        return features

    @staticmethod
    def combine_base_and_advanced_results(base_result: Dict[str, Any], 
                                        advanced_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        将基础分析结果和高级分析结果合并
        
        Args:
            base_result: 基础分析结果
            advanced_result: 高级分析结果
            
        Returns:
            合并后的结果
        """
        combined_result = {
            # 基础信息
            "timestamp": base_result.get("timestamp", ""),
            "window_start_time": base_result.get("window_start_time", ""),
            "window_end_time": base_result.get("window_end_time", ""),
            
            # 基础分析结果
            "base_behavior": base_result.get("behavior", "normal"),
            "base_confidence": base_result.get("confidence", 0.85),
            "detected_all": base_result.get("detected_all", []),
            
            # 高级分析结果
            "advanced_behavior": advanced_result.get("advanced_behavior", "normal"),
            "advanced_confidence": advanced_result.get("confidence", 0.85),
            "probabilities": advanced_result.get("probabilities", {}),
            "comparison": advanced_result.get("comparison", "未知"),
            
            # 原始数据
            "raw_data": base_result.get("raw_data", {})
        }
        
        # 添加错误信息（如果有的话）
        if "error" in base_result:
            combined_result["base_error"] = base_result["error"]
        if "error" in advanced_result:
            combined_result["advanced_error"] = advanced_result["error"]
            
        return combined_result


def demonstrate_integration():
    """
    演示如何集成base_analyzer.py和analysis.py
    """
    print("演示基础分析器与高级分析器的集成")
    
    # 示例数据
    sample_data = {
        "timestamp": 1234567890.0,
        "ax": 0.5,
        "ay": 0.1,
        "az": 9.8,
        "gx": 0.01,
        "gy": 0.02,
        "gz": 0.03,
        "speed": 60.0,
        "wheel": 5.0,
        "cnt": 100
    }
    
    # 假设这是base_analyzer.py的输出
    base_result_example = {
        "timestamp": "2025-08-04T10:30:30.123456",
        "window_start_time": "2025-08-04T10:30:20.123456",
        "window_end_time": "2025-08-04T10:30:30.123456",
        "behavior": "匀速直线",
        "confidence": 0.92,
        "raw_data": sample_data,
        "detected_all": ["匀速直线", "车道保持"]
    }
    
    # 适配结果
    adapted_result = AnalyzerAdapter.adapt_base_result_for_advanced_analysis(base_result_example)
    
    print("原始基础分析结果:")
    print(f"  行为: {base_result_example['behavior']}")
    print(f"  置信度: {base_result_example['confidence']}")
    print(f"  时间戳: {base_result_example['timestamp']}")
    
    print("\n适配后的结果:")
    print(f"  行为: {adapted_result['behavior']}")
    print(f"  置信度: {adapted_result['confidence']}")
    print(f"  时间戳: {adapted_result['timestamp']}")
    
    # 提取特征
    features = AnalyzerAdapter.extract_features_from_base_result(base_result_example)
    print("\n提取的特征:")
    print(features.to_string(index=False))
    
    # 模拟高级分析结果
    advanced_result_example = {
        "advanced_behavior": "安全驾驶",
        "confidence": 0.95,
        "probabilities": {
            "安全驾驶": 0.95,
            "危险驾驶": 0.03,
            "激进驾驶": 0.02
        },
        "comparison": "一致"
    }
    
    # 合并结果
    combined_result = AnalyzerAdapter.combine_base_and_advanced_results(
        base_result_example, advanced_result_example)
    
    print("\n合并后的完整结果:")
    print(f"  基础行为: {combined_result['base_behavior']}")
    print(f"  高级行为: {combined_result['advanced_behavior']}")
    print(f"  一致性: {combined_result['comparison']}")
    print(f"  时间窗口: {combined_result['window_start_time']} 到 {combined_result['window_end_time']}")


if __name__ == "__main__":
    demonstrate_integration()