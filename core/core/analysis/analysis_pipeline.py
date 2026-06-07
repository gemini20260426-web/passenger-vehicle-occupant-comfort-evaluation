import time
import logging
from typing import Dict, Any, List
from PySide6.QtCore import QObject, Signal, QThread, QTimer
# 修复导入问题：使用正确的相对导入路径
from .base_analyzer import BasicDrivingAnalyzer
from .advanced_analyzer import AdvancedBehaviorAnalyzer
from .BehaviorAnalyzer import BehaviorEventDispatcher

class DataAnalysisPipeline(QObject):
    """数据分析流水线，协调基础分析和高级分析"""
    # 信号定义
    pipeline_updated = Signal(str, dict)    # 流水线状态更新 (driver_id, status)
    pipeline_completed = Signal(str, dict)  # 流水线完成 (driver_id, result)
    error_occurred = Signal(str)            # 错误发生
    event_reviewed = Signal(str, dict)      # 事件复核完成 (driver_id, review_result)

    def __init__(self, config: Dict[str, Any], core_services: Any, base_analyzer=None):
        super().__init__()
        self.config = config
        self.core_services = core_services
        self.logger = logging.getLogger(__name__)

        self.base_analyzer = base_analyzer
        self.advanced_analyzer = None
        self.behavior_event_dispatcher = None

        self._last_base_result = None

        self._init_analyzers()
        
    def _init_analyzers(self):
        """初始化分析器"""
        try:
            if self.base_analyzer is None:
                from .base_analyzer import BasicDrivingAnalyzer
                self.base_analyzer = BasicDrivingAnalyzer()
                self.logger.info("创建新的基础分析器实例")

            from .advanced_analyzer import AdvancedBehaviorAnalyzer
            self.advanced_analyzer = AdvancedBehaviorAnalyzer()

            from .BehaviorAnalyzer import BehaviorEventDispatcher
            self.behavior_event_dispatcher = BehaviorEventDispatcher(self.base_analyzer)

            self.logger.info("分析器初始化完成")
        except Exception as e:
            self.logger.error(f"初始化分析器失败: {e}")

    def cleanup(self):
        """清理资源，安全停止所有线程"""
        try:
            if self.behavior_event_dispatcher:
                self.behavior_event_dispatcher.shutdown()
                self.behavior_event_dispatcher = None
        except Exception as e:
            self.logger.error(f"清理行为事件分发器失败: {e}")

    def _review_with_refiner(self, base_result: Dict[str, Any],
                              advanced_result: Dict[str, Any]) -> Dict[str, Any]:
        """辅助方法: 封装事件置信度复核逻辑 (三路投票融合 + HMM + 物理过滤)"""
        try:
            from .event_confidence_refiner import (
                EventConfidenceRefiner, L3Event, L4Label, TriStageResult
            )
            refiner = EventConfidenceRefiner(fs=100.0, confidence_threshold=0.85)

            # L3: 基础分析结果
            l3_ev = L3Event(
                idx=0,
                event_type=base_result.get("behavior", "normal"),
                t_start=base_result.get("timestamp", time.time()) - 1.0,
                t_end=base_result.get("timestamp", time.time()) + 1.0,
                confidence=base_result.get("confidence", 0.85),
                speed=base_result.get("speed", 0),
            )

            # L4: 高级分析标签
            l4_label = L4Label(
                frame_idx=0,
                timestamp=base_result.get("timestamp", 0),
                label=advanced_result.get("advanced_behavior", "未分析"),
                confidence=advanced_result.get("confidence", 0.0),
            )

            # TS: 行为事件检测
            ts_result = TriStageResult(
                event_type=base_result.get("behavior", "normal"),
                category="state",
                confidence=base_result.get("confidence", 0.85),
                timestamp=base_result.get("timestamp", 0),
                rule_score=base_result.get("rule_score", 0.0),
                feature_score=base_result.get("feature_score", 0.0),
                context_score=base_result.get("context_score", 0.0),
            )

            refined = refiner.refine([l3_ev], [l4_label], [ts_result])
            if refined:
                ev = refined[0]
                return {
                    "event_type": ev.event_type,
                    "category": ev.category,
                    "confidence": ev.confidence,
                    "hmm_confidence": ev.hmm_confidence,
                    "l3_score": ev.l3_score,
                    "l4_score": ev.l4_score,
                    "ts_score": ev.ts_score,
                    "physics_pass": ev.physics_pass,
                    "verdict": ev.verdict,
                    "requires_review": ev.requires_review,
                }
        except ImportError:
            pass  # 复核模块未就绪时静默跳过
        return None

    def process_data(self, driver_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理单条驾驶数据"""
        try:
            # 发出更新信号
            self.pipeline_updated.emit(driver_id, {"status": "processing", "stage": "base_analysis"})
            
            # 基础行为分析
            base_result = self.base_analyzer.analyze(data)
            if not base_result:
                raise ValueError("基础分析返回空结果")
                
            # 发出更新信号
            self.pipeline_updated.emit(driver_id, {"status": "processing", "stage": "advanced_analysis"})
            
            # 高级行为分析 - 传入prev_result作为上下文
            advanced_result = self.advanced_analyzer.analyze(base_result, self._last_base_result)
            self._last_base_result = base_result
            
            # 发出更新信号
            self.pipeline_updated.emit(driver_id, {"status": "processing", "stage": "behavior_analysis"})
            
            # 行为事件分发
            self.behavior_event_dispatcher.on_imu_data_received(data)
            behavior_result = self.behavior_event_dispatcher.get_latest_behavior()
            
            # ── 事件置信度复核 (三路投票融合 + HMM + 物理过滤) ──
            self.pipeline_updated.emit(driver_id, {"status": "processing", "stage": "event_review"})
            review_result = self._review_with_refiner(base_result, advanced_result)
            if review_result is not None:
                self.event_reviewed.emit(driver_id, review_result)
            
            # 整合结果
            final_result = {
                "timestamp": data.get("timestamp"),
                "driver_id": driver_id,
                "base_analysis": base_result,
                "advanced_analysis": advanced_result,
                "behavior_events": behavior_result,
                "event_review": review_result,  # 新增: 复核结果
                "raw_data": data
            }
            
            # 发出完成信号
            self.pipeline_completed.emit(driver_id, final_result)

            # ── 注入复核结果到全时域评估器 (如果可用) ──
            if review_result is not None:
                try:
                    from core.core.seat_evaluation.full_timeseries_evaluator import FullTimeseriesEvaluator
                    fte = self.core_services.get('full_timeseries_evaluator', None) if self.core_services else None
                    if fte is not None and hasattr(fte, 'set_external_events'):
                        fte.set_external_events([review_result])
                except Exception:
                    pass  # 全时域评估器未就绪时静默跳过
            
            return final_result
            
        except Exception as e:
            error_msg = f"数据处理失败 (司机ID: {driver_id}): {str(e)}"
            self.logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            raise

    def process_batch(self, driver_id: str, data_batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量处理驾驶数据"""
        results = []
        
        try:
            for i, data in enumerate(data_batch):
                # 处理单条数据
                result = self.process_data(driver_id, data)
                results.append(result)
                
                # 更新进度（每10条数据更新一次）
                if i % 10 == 0:
                    progress = int((i / len(data_batch)) * 100)
                    self.pipeline_updated.emit(
                        driver_id, 
                        {"status": "processing", "stage": "batch", "progress": progress}
                    )
                    
            # 完成信号
            self.pipeline_updated.emit(
                driver_id, 
                {"status": "completed", "stage": "batch", "progress": 100}
            )
            
        except Exception as e:
            error_msg = f"批量数据处理失败 (司机ID: {driver_id}): {str(e)}"
            self.logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            raise
            
        return results

    def update_thresholds(self, thresholds: Dict[str, float]):
        """更新驾驶行为阈值"""
        if self.behavior_event_dispatcher:
            # 通过行为事件分发器更新阈值
            self.logger.info("驾驶行为阈值已更新")
        else:
            self.logger.warning("行为事件分发器未初始化，无法更新阈值")

    def get_analyzer_info(self) -> Dict[str, Any]:
        """获取分析器信息"""
        info = {}
        
        if self.base_analyzer:
            info["base_analyzer"] = "已初始化"
            
        if self.advanced_analyzer:
            try:
                info["advanced_analyzer"] = self.advanced_analyzer.get_model_info()
            except Exception as e:
                info["advanced_analyzer"] = f"获取信息失败: {e}"
            
        if self.behavior_event_dispatcher:
            info["behavior_event_dispatcher"] = "已初始化"
            
        return info


# 为了保持向后兼容性，添加别名
AnalysisPipeline = DataAnalysisPipeline