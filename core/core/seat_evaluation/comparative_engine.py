#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对照分析引擎
支持实验组vs对照组对比分析
"""

import json
import os
import time
import numpy as np
import logging
import warnings
from typing import Dict, Any, Optional, List
from PySide6.QtCore import QObject, Signal

from .engine_v2 import MultiChannelSeatEvaluationEngine
from ..analysis.core_types import (
    ComparativeEvaluationTrigger, ComparativeEvaluationResult, TestGroupReport
)

logger = logging.getLogger(__name__)


class ComparativeEvaluationEngine(QObject):
    """对照分析引擎 v1.0 — [已弃用] 请使用 comparative_engine_v2.MultiChannelComparativeEngine
    
    自 v3.5 起，本引擎已弃用。所有新代码应直接使用 comparative_engine_v2.MultiChannelComparativeEngine。
    """
    
    comparison_started = Signal(dict)
    comparison_completed = Signal(dict)
    metric_comparison_updated = Signal(dict)
    
    def __init__(self, config_manager=None, data_storage=None):
        super().__init__()
        warnings.warn(
            "ComparativeEvaluationEngine is deprecated. Use MultiChannelComparativeEngine from comparative_engine_v2 instead.",
            DeprecationWarning, stacklevel=2
        )
        self.config_manager = config_manager
        self.data_storage = data_storage
        
        # 初始化座椅评测引擎
        self.evaluation_engine = MultiChannelSeatEvaluationEngine(config_manager, data_storage)
        
        # 历史结果缓存
        self.results_cache: Dict[str, Dict[str, Any]] = {}
        
        # JSON 文件备份路径
        self._json_backup_dir = self._resolve_backup_dir()
        
        logger.info("对照分析引擎初始化完成")
    
    def _resolve_backup_dir(self) -> str:
        """解析 JSON 备份目录"""
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))),
            'data_output', 'comparative_reports'
        )
        os.makedirs(output_dir, exist_ok=True)
        return output_dir
    
    def compare_groups(self, trigger: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        对比两组数据
        
        Args:
            trigger: 对比触发器字典
            
        Returns:
            对比结果字典
        """
        try:
            self.comparison_started.emit(trigger)
            
            comparison_id = trigger.get('comparison_id', '')
            experimental_data = trigger.get('experimental_data', {})
            control_data = trigger.get('control_data', {})
            metrics = trigger.get('metrics', [])
            
            # 分别评测两组
            exp_result = self._evaluate_single_group(
                experimental_data, metrics, 'experimental'
            )
            ctrl_result = self._evaluate_single_group(
                control_data, metrics, 'control'
            )
            
            if not exp_result or not ctrl_result:
                logger.warning(f"评测结果不完整: {comparison_id}")
                return None
            
            # 计算对比指标
            comparison_metrics = self._compute_comparison_metrics(
                exp_result.get('metrics', {}), ctrl_result.get('metrics', {})
            )
            
            # 生成报告
            report = self._generate_comparison_report(
                exp_result, ctrl_result, comparison_metrics, comparison_id
            )
            
            # 发送信号
            self.comparison_completed.emit(report)
            
            logger.info(f"对照分析完成: {comparison_id}")
            
            return report
            
        except Exception as e:
            logger.error(f"对照分析失败: {e}", exc_info=True)
            return None
    
    def _evaluate_single_group(self, data: Dict[str, Any], 
                              metrics: List[str], group_tag: str) -> Optional[Dict[str, Any]]:
        """
        评测单组数据
        
        Args:
            data: 数据
            metrics: 指标列表
            group_tag: 组标签
            
        Returns:
            评测结果
        """
        try:
            # 构造评测触发器
            eval_trigger = {
                'event_id': f"{group_tag}_eval",
                'event_type': 'single_evaluation',
                'metrics': metrics,
                'raw_data': data,
                'data_window': {'pre': 0.5, 'post': 1.5}
            }
            
            # 执行评测
            result = self.evaluation_engine.evaluate_by_event(eval_trigger)
            
            if result:
                result['group_tag'] = group_tag
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"评测 {group_tag} 组失败: {e}")
            return None
    
    def _compute_comparison_metrics(self, exp_metrics: Dict[str, float], 
                                   ctrl_metrics: Dict[str, float]) -> Dict[str, Any]:
        """
        计算对比指标
        
        Args:
            exp_metrics: 实验组指标
            ctrl_metrics: 对照组指标
            
        Returns:
            对比指标字典
        """
        comparisons = {}
        
        for metric_id in exp_metrics.keys():
            if metric_id in ctrl_metrics:
                exp_val = exp_metrics[metric_id]
                ctrl_val = ctrl_metrics[metric_id]
                
                # 计算相对差异 (正数=改进，与AttenuationOperator一致)
                if ctrl_val != 0:
                    relative_diff = ((ctrl_val - exp_val) / ctrl_val) * 100.0
                else:
                    relative_diff = 0.0 if exp_val == 0 else -100.0
                
                # 判断改进方向 (假设指标越小越好)
                improved = exp_val < ctrl_val
                
                comparisons[metric_id] = {
                    'experimental': exp_val,
                    'control': ctrl_val,
                    'absolute_diff': exp_val - ctrl_val,
                    'relative_diff': relative_diff,
                    'improved': improved
                }
                
                # 发送指标对比更新信号
                self.metric_comparison_updated.emit({
                    'metric_id': metric_id,
                    'data': comparisons[metric_id]
                })
        
        return comparisons
    
    def _generate_comparison_report(self, exp_result: Dict[str, Any], 
                                   ctrl_result: Dict[str, Any], 
                                   comparison_metrics: Dict[str, Any],
                                   comparison_id: str) -> Dict[str, Any]:
        """
        生成对比报告
        
        Args:
            exp_result: 实验组结果
            ctrl_result: 对照组结果
            comparison_metrics: 对比指标
            comparison_id: 对比ID
            
        Returns:
            报告字典
        """
        # 计算总体改进分数
        overall_improvement = self._calculate_overall_improvement(comparison_metrics)
        
        # 统计改进指标数量
        improved_count = sum(1 for m in comparison_metrics.values() if m.get('improved', False))
        total_count = len(comparison_metrics)
        
        report = {
            'comparison_id': comparison_id,
            'timestamp': exp_result.get('timestamp', 0.0),
            'experimental_result': exp_result,
            'control_result': ctrl_result,
            'comparison_metrics': comparison_metrics,
            'overall_improvement': overall_improvement,
            'improved_metrics_count': improved_count,
            'total_metrics_count': total_count,
            'summary': self._generate_summary(comparison_metrics, overall_improvement)
        }
        
        return report
    
    def _calculate_overall_improvement(self, comparison_metrics: Dict[str, Any]) -> float:
        """
        计算总体改进分数
        
        Args:
            comparison_metrics: 对比指标
            
        Returns:
            总体改进分数 (-100到+100，正数表示改进)
        """
        if not comparison_metrics:
            return 0.0
        
        # 简单加权平均
        weights = {
            'SEAT_Z': 0.15,
            'SEAT_XY': 0.10,
            'VDV_Z': 0.15,
            'AW_Z': 0.10,
            'HIC15': 0.10,
            'ACC_H_PEAK': 0.10,
            'FDS_D': 0.10,
            'R_FACTOR': 0.10,
            'ACC_RMS': 0.05,
            'ACC_PEAK': 0.05,
        }
        
        total_weight = 0.0
        weighted_improvement = 0.0
        
        for metric_id, data in comparison_metrics.items():
            weight = weights.get(metric_id, 1.0 / len(comparison_metrics))

            # relative_diff: 正数表示改进 (实验组 < 对照组)
            improvement = data.get('relative_diff', 0.0)
            weighted_improvement += improvement * weight
            total_weight += weight
        
        if total_weight > 0:
            return weighted_improvement / total_weight
        return 0.0
    
    def _generate_summary(self, comparison_metrics: Dict[str, Any], 
                        overall_improvement: float) -> str:
        """
        生成摘要文本
        
        Args:
            comparison_metrics: 对比指标
            overall_improvement: 总体改进分数
            
        Returns:
            摘要字符串
        """
        improved_count = sum(1 for m in comparison_metrics.values() if m.get('improved', False))
        total_count = len(comparison_metrics)
        
        if overall_improvement > 5:
            status = "显著提升"
        elif overall_improvement > 0:
            status = "有所改善"
        elif overall_improvement > -5:
            status = "基本持平"
        else:
            status = "有所下降"
        
        summary = f"总体表现: {status} (改进分数: {overall_improvement:.1f}%)\n"
        summary += f"改进指标: {improved_count}/{total_count}\n"
        
        # 列出关键指标
        key_metrics = ['SEAT_Z', 'HIC15', 'ACC_H_PEAK', 'FDS_D']
        for metric_id in key_metrics:
            if metric_id in comparison_metrics:
                data = comparison_metrics[metric_id]
                rel_diff = data.get('relative_diff', 0.0)
                if abs(rel_diff) < 1.0:
                    arrow = "→"
                elif rel_diff > 0:
                    arrow = "↑"
                else:
                    arrow = "↓"
                summary += f"  {metric_id}: {rel_diff:+.1f}% {arrow}\n"
        
        return summary
    
    def save_comparison_report(self, report: Dict[str, Any]) -> bool:
        """
        保存对比报告
        
        保存策略:
        1. 优先使用 data_storage (EvaluationResultStore) 持久化到 SQLite
        2. 同时缓存到内存 results_cache
        3. 同时备份到 JSON 文件 (兜底)
        
        Args:
            report: 报告字典
            
        Returns:
            是否成功
        """
        try:
            comparison_id = report.get('comparison_id', '')
            if not comparison_id:
                comparison_id = f"cmp_{int(time.time() * 1000)}"
                report['comparison_id'] = comparison_id
            
            # 写入内存缓存
            self.results_cache[comparison_id] = report
            
            # 1. 持久化到 SQLite (通过 data_storage)
            db_saved = False
            if self.data_storage is not None:
                try:
                    if hasattr(self.data_storage, 'save_event'):
                        self.data_storage.save_event(
                            session_id=report.get('timestamp', 'default'),
                            event_id=comparison_id,
                            event_type='comparative_analysis',
                            group_tag='comparison',
                            event_label=report.get('summary', ''),
                            event_timestamp=report.get('timestamp', time.time()),
                            overall_score=report.get('overall_improvement'),
                            overall_grade=self._improvement_to_grade(
                                report.get('overall_improvement', 0.0)
                            ),
                            summary=report.get('summary', ''),
                            raw_payload=report
                        )
                        db_saved = True
                    elif hasattr(self.data_storage, 'save'):
                        self.data_storage.save(comparison_id, report)
                        db_saved = True
                except Exception as e:
                    logger.warning(f"SQLite 保存失败, 回退到 JSON: {e}")
            
            # 2. JSON 文件备份 (兜底)
            json_path = os.path.join(
                self._json_backup_dir, f"{comparison_id}.json"
            )
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(
                f"对比报告已保存: {comparison_id} "
                f"(db={db_saved}, json={json_path})"
            )
            return True
            
        except Exception as e:
            logger.error(f"保存对比报告失败: {e}")
            return False
    
    def load_comparison_reports(self, 
                                 limit: int = 100,
                                 offset: int = 0) -> List[Dict[str, Any]]:
        """
        加载历史对比报告
        
        加载策略:
        1. 优先从 data_storage (SQLite) 加载
        2. 回退到内存缓存
        3. 回退到 JSON 文件扫描
        
        Args:
            limit: 最大返回数量
            offset: 偏移量
            
        Returns:
            报告列表
        """
        reports = []
        
        # 1. 尝试从 SQLite 加载
        if self.data_storage is not None and hasattr(self.data_storage, '_get_conn'):
            try:
                conn = self.data_storage._get_conn()
                rows = conn.execute(
                    """SELECT raw_payload FROM evaluation_events
                       WHERE event_type = 'comparative_analysis'
                       ORDER BY event_timestamp DESC
                       LIMIT ? OFFSET ?""",
                    (limit, offset)
                ).fetchall()
                for row in rows:
                    try:
                        payload = json.loads(row[0]) if row[0] else None
                        if payload and isinstance(payload, dict):
                            reports.append(payload)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if reports:
                    return reports
            except Exception as e:
                logger.debug(f"SQLite 加载失败: {e}")
        
        # 2. 内存缓存
        if not reports:
            cached = list(self.results_cache.values())
            if cached:
                cached.sort(
                    key=lambda r: r.get('timestamp', 0.0), reverse=True
                )
                reports = cached[offset:offset + limit]
        
        # 3. JSON 文件扫描
        if not reports and os.path.isdir(self._json_backup_dir):
            json_files = sorted(
                [f for f in os.listdir(self._json_backup_dir) if f.endswith('.json')],
                reverse=True
            )
            loaded = 0
            for fname in json_files:
                if loaded >= limit:
                    break
                try:
                    fpath = os.path.join(self._json_backup_dir, fname)
                    with open(fpath, 'r', encoding='utf-8') as f:
                        report = json.load(f)
                    if isinstance(report, dict):
                        reports.append(report)
                        loaded += 1
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"JSON 加载失败 {fname}: {e}")
        
        return reports
    
    def delete_comparison_report(self, comparison_id: str) -> bool:
        """
        删除对比报告
        
        Args:
            comparison_id: 对比报告ID
            
        Returns:
            是否成功
        """
        try:
            # 从内存缓存删除
            self.results_cache.pop(comparison_id, None)
            
            # 从 SQLite 删除
            if self.data_storage is not None and hasattr(self.data_storage, '_get_conn'):
                try:
                    conn = self.data_storage._get_conn()
                    conn.execute(
                        "DELETE FROM evaluation_events WHERE event_id = ?",
                        (comparison_id,)
                    )
                    conn.commit()
                except Exception as e:
                    logger.warning(f"SQLite 删除失败: {e}")
            
            # 从 JSON 文件删除
            json_path = os.path.join(
                self._json_backup_dir, f"{comparison_id}.json"
            )
            if os.path.exists(json_path):
                os.remove(json_path)
            
            logger.info(f"对比报告已删除: {comparison_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除对比报告失败: {e}")
            return False
    
    def get_saved_reports(self) -> List[Dict[str, Any]]:
        """
        获取已保存的报告列表 (从内存缓存)
        
        Returns:
            报告列表
        """
        return list(self.results_cache.values())
    
    @staticmethod
    def _improvement_to_grade(improvement: float) -> str:
        """将改进分数转换为等级"""
        if improvement > 10:
            return 'A'
        elif improvement > 5:
            return 'B'
        elif improvement > -5:
            return 'C'
        elif improvement > -10:
            return 'D'
        else:
            return 'E'
