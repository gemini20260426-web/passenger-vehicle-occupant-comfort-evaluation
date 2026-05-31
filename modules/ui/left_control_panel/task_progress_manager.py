#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局任务进度管理器
统一管理左侧面板所有模块的任务进度状态
切换标签页时自动恢复对应模块的进度显示
"""

import logging
from typing import Dict, Optional, Callable

logger = logging.getLogger(__name__)


class TaskProgressManager:
    """全局任务进度管理器 - 单例模式"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._module_states: Dict[str, dict] = {}
        self._active_module: str = ""
        self._ui_updater: Optional[Callable] = None

        logger.info("TaskProgressManager 全局单例已初始化")

    def set_ui_updater(self, updater: Callable[[str, int, str], None]):
        """设置UI更新回调 (task_name, progress, detail)"""
        self._ui_updater = updater

    def register_module(self, module_name: str):
        """注册模块"""
        if module_name not in self._module_states:
            self._module_states[module_name] = {
                "task_name": "等待启动",
                "progress": 0,
                "detail": ""
            }
            logger.info(f"任务进度管理器已注册模块: {module_name}")

    def update_progress(self, module_name: str, task_name: str = None,
                        progress: int = None, detail: str = None):
        """更新模块任务进度"""
        if module_name not in self._module_states:
            self.register_module(module_name)

        state = self._module_states[module_name]
        if task_name is not None:
            state["task_name"] = task_name
        if progress is not None:
            state["progress"] = max(0, min(100, progress))
        if detail is not None:
            state["detail"] = detail

        if module_name == self._active_module:
            self._apply_to_ui(state)

    def reset_module(self, module_name: str):
        """重置模块进度"""
        if module_name in self._module_states:
            self._module_states[module_name] = {
                "task_name": "等待启动",
                "progress": 0,
                "detail": ""
            }
        if module_name == self._active_module:
            self._apply_to_ui(self._module_states.get(module_name, {}))

    def set_active_module(self, module_name: str):
        """切换活跃模块"""
        if module_name == self._active_module:
            return
        self._active_module = module_name
        if module_name not in self._module_states:
            self.register_module(module_name)
        state = self._module_states[module_name]
        self._apply_to_ui(state)
        logger.info(f"任务进度切换至模块: {module_name}")

    def get_active_module(self) -> str:
        """获取当前活跃模块名"""
        return self._active_module

    def _apply_to_ui(self, state: dict):
        """将状态应用到UI"""
        if self._ui_updater:
            try:
                self._ui_updater(
                    state.get("task_name", ""),
                    state.get("progress", 0),
                    state.get("detail", "")
                )
            except Exception as e:
                logger.error(f"更新任务进度UI失败: {e}")

    @classmethod
    def reset_instance(cls):
        """重置单例（仅用于测试）"""
        cls._instance = None
