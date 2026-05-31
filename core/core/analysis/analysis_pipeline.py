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
            
            # 整合结果
            final_result = {
                "timestamp": data.get("timestamp"),
                "driver_id": driver_id,
                "base_analysis": base_result,
                "advanced_analysis": advanced_result,
                "behavior_events": behavior_result,
                "raw_data": data
            }
            
            # 发出完成信号
            self.pipeline_completed.emit(driver_id, final_result)
            
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