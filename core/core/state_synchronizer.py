import logging
from collections import deque
from PySide6.QtCore import QTimer
from typing import Dict, Any
import time

logger = logging.getLogger(__name__)

class StateSynchronizer:
    """状态同步器"""
    
    def __init__(self, left_panels: Dict[str, Any], right_panel: Any):
        print("StateSynchronizer init called")  # 测试打印
        self.left_panels = left_panels
        self.right_panel = right_panel
        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self._sync_all_panels)
        print("Connected to _sync_all_panels")  # 测试
        self.sync_interval = 200  # 缩短同步间隔以提高实时性
        self.panel_states = {}
        self.state_history = deque(maxlen=100)
    
    def start_sync(self):
        """启动同步"""
        self.sync_timer.start(self.sync_interval)
        logger.info("状态同步已启动")
    
    def stop_sync(self):
        """停止同步"""
        self.sync_timer.stop()
        logger.info("状态同步已停止")
    
    def _sync_all_panels(self):
        print(" _sync_all_panels called")  # 测试 
        try:
            # 收集右侧面板的最新状态
            right_panel_state = self._get_right_panel_state()
            
            # 更新左侧面板
            for panel_id, panel in self.left_panels.items():
                self._update_panel_state(panel_id, panel, right_panel_state)
            
            # 收集左侧面板的状态
            left_panels_state = self._collect_left_panels_state()
            
            # 更新右侧面板
            self._update_right_panel(left_panels_state)
            
            # 记录状态历史
            self.state_history.append({
                'timestamp': time.time(),
                'right_panel_state': right_panel_state,
                'left_panels_state': left_panels_state
            })
            
            logger.info("面板状态同步完成")
        except Exception as e:
            logger.error(f"面板状态同步失败: {e}")
    
    def _get_right_panel_state(self) -> Dict[str, Any]:
        """获取右侧面板状态"""
        try:
            if hasattr(self.right_panel, 'get_state'):
                return self.right_panel.get_state()
            else:
                return {}
        except Exception as e:
            logger.error(f"获取右侧面板状态失败: {e}")
            return {}
    
    def _collect_left_panels_state(self) -> Dict[str, Dict[str, Any]]:
        """收集左侧面板状态"""
        states = {}
        for panel_id, panel in self.left_panels.items():
            try:
                if hasattr(panel, 'get_state'):
                    states[panel_id] = panel.get_state()
                else:
                    states[panel_id] = {}
            except Exception as e:
                logger.error(f"获取左侧面板 {panel_id} 状态失败: {e}")
                states[panel_id] = {}
        return states
    
    def _update_panel_state(self, panel_id: str, panel: Any, state: Dict[str, Any]):
        """更新单个面板状态"""
        try:
            if hasattr(panel, 'update_state'):
                panel.update_state(state)
                logger.debug(f"更新左侧面板 {panel_id} 状态成功")
        except Exception as e:
            logger.error(f"更新左侧面板 {panel_id} 状态失败: {e}")
    
    def _update_right_panel(self, state: Dict[str, Dict[str, Any]]):
        """更新右侧面板状态"""
        try:
            if hasattr(self.right_panel, 'update_state'):
                self.right_panel.update_state(state)
                logger.debug("更新右侧面板状态成功")
        except Exception as e:
            logger.error(f"更新右侧面板状态失败: {e}") 
