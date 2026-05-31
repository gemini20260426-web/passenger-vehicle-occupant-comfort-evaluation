"""驾驶行为分析流水线（协调各分析组件的执行流程）"""
import logging
from typing import Dict, Any, Optional
from PySide6.QtCore import QObject, Signal, QMutexLocker
from .BehaviorAnalyzer import BehaviorAnalyzer
from .BehaviorEvaluator import BehaviorEvaluator
from .BehaviorImprovementSystem import BehaviorImprovementSystem
from common.exceptions import PipelineError

class AnalysisPipeline(QObject):
    """分析流水线控制器，协调各分析组件的执行"""
    pipeline_updated = Signal(str, str)  # 司机ID, 状态
    pipeline_completed = Signal(str, dict)  # 司机ID, 分析结果

    def __init__(self, config: Dict[str, Any], core_services):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.core_services = core_services
        self.pipeline_lock = core_services.get_lock('analysis_pipeline')
        
        # 初始化分析组件
        self.behavior_analyzer = BehaviorAnalyzer(config.get('analysis_thresholds', {}))
        self.behavior_evaluator = BehaviorEvaluator()
        self.improvement_system = BehaviorImprovementSystem(core_services)
        
        # 连接组件信号
        self._connect_signals()

    def _connect_signals(self) -> None:
        """连接各组件的信号与槽"""
        self.behavior_analyzer.behavior_detected.connect(
            self.behavior_evaluator.add_behavior_event
        )
        self.behavior_analyzer.analysis_error.connect(self._handle_analysis_error)
        self.improvement_system.improvement_analysis_completed.connect(
            self._on_improvement_completed
        )

    def process_realtime_data(self, driver_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理实时驾驶数据"""
        try:
            with QMutexLocker(self.pipeline_lock):
                self.pipeline_updated.emit(driver_id, "processing")
                
                # 1. 行为检测
                behaviors = self.behavior_analyzer.analyze_data(data)
                if not behaviors:
                    return None
                    
                # 2. 实时评估
                current_eval = self.behavior_evaluator.get_current_evaluation()
                
                # 3. 生成实时反馈
                feedback = self._generate_realtime_feedback(behaviors, current_eval)
                return {
                    'driver_id': driver_id,
                    'timestamp': data.get('timestamp'),
                    'behaviors': behaviors,
                    'current_evaluation': current_eval,
                    'feedback': feedback
                }
                
        except Exception as e:
            error_msg = f"实时数据处理失败: {str(e)}"
            self.logger.error(error_msg)
            self.pipeline_updated.emit(driver_id, "error")
            return None

    def run_complete_analysis(self, driver_id: str, time_range: str = 'weekly') -> None:
        """执行完整的驾驶行为分析流程"""
        self.pipeline_updated.emit(driver_id, "analyzing")
        self.improvement_system.analyze_driver_behavior(driver_id, time_range)

    def _generate_realtime_feedback(self, behaviors: list, evaluation: Optional[dict]) -> str:
        """生成实时驾驶反馈"""
        if not behaviors:
            return "当前驾驶行为正常"
            
        feedback = []
        for behavior in behaviors:
            feedback.append(f"检测到{behavior['event_type']}，严重程度：{behavior['severity']}")
            
        if evaluation and evaluation['level'] in ['较差', '差']:
            feedback.append("注意：当前驾驶评分较低，请改善驾驶习惯")
            
        return "; ".join(feedback)

    def _on_improvement_completed(self, driver_id: str) -> None:
        """改进分析完成回调"""
        result = self.improvement_system.get_analysis_result(driver_id)
        self.pipeline_completed.emit(driver_id, result)
        self.pipeline_updated.emit(driver_id, "completed")

    def _handle_analysis_error(self, error_msg: str) -> None:
        """处理分析错误"""
        self.logger.error(f"流水线错误: {error_msg}")
        self.pipeline_updated.emit("", f"error: {error_msg}")
