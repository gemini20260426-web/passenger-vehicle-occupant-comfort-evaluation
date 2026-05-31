#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步UI组件加载器 - 解决UI线程阻塞问题
在后台线程中预加载重量级UI组件，完成后安全切换到主线程
"""

import logging
import time
from typing import Callable, Optional, Dict, Any, Type
from collections import deque

from PySide6.QtCore import (
    QObject, Signal, QTimer, QThread, QCoreApplication,
    QMutex, QMutexLocker
)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PySide6.QtCore import Qt


class UILoadTask(QObject):
    """UI加载任务"""
    finished = Signal(object, str)
    error = Signal(str, str)

    def __init__(self, component_class: Type[QWidget], component_name: str, 
                 init_args: tuple = (), init_kwargs: dict = None):
        super().__init__()
        self.component_class = component_class
        self.component_name = component_name
        self.init_args = init_args
        self.init_kwargs = init_kwargs or {}
        self.result_widget = None


class UILoaderWorker(QThread):
    """UI加载工作线程"""
    component_loaded = Signal(object, str)
    load_error = Signal(str, str)

    def __init__(self, component_class: Type[QWidget], component_name: str,
                 init_args: tuple = (), init_kwargs: dict = None):
        super().__init__()
        self.component_class = component_class
        self.component_name = component_name
        self.init_args = init_args
        self.init_kwargs = init_kwargs or {}
        self.logger = logging.getLogger(__name__)

    def run(self):
        try:
            self.logger.info(f"开始异步加载UI组件: {self.component_name}")
            start_time = time.time()
            
            QApplication.processEvents()
            
            widget = self.component_class(*self.init_args, **self.init_kwargs)
            
            QApplication.processEvents()
            
            elapsed = time.time() - start_time
            self.logger.info(f"UI组件加载完成: {self.component_name}, 耗时: {elapsed:.2f}s")
            
            self.component_loaded.emit(widget, self.component_name)
        except Exception as e:
            self.logger.error(f"UI组件加载失败: {self.component_name}, 错误: {e}")
            self.load_error.emit(self.component_name, str(e))


class AsyncUILoader(QObject):
    """
    异步UI组件加载器
    
    功能：
    1. 在后台线程中加载重量级UI组件
    2. 加载过程中显示占位符
    3. 加载完成后安全替换占位符
    4. 支持组件预加载队列
    5. 支持加载进度回调
    """
    component_ready = Signal(object, str)
    component_failed = Signal(str, str)
    loading_started = Signal(str)
    loading_progress = Signal(str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self._mutex = QMutex()
        
        self._pending_loads: deque = deque()
        self._loading_components: Dict[str, UILoaderWorker] = {}
        self._loaded_components: Dict[str, QWidget] = {}
        self._placeholders: Dict[str, QWidget] = {}
        
        self._max_concurrent_loads = 2
        self._process_timer = QTimer(self)
        self._process_timer.timeout.connect(self._process_load_queue)
        self._process_timer.start(100)
        
        self.logger.info("✅ 异步UI加载器已初始化")

    def load_component_async(self, component_class: Type[QWidget], component_name: str,
                            placeholder_widget: Optional[QWidget] = None,
                            parent_widget: Optional[QWidget] = None,
                            init_args: tuple = (), init_kwargs: dict = None,
                            callback: Optional[Callable] = None) -> str:
        """
        异步加载UI组件
        
        Args:
            component_class: 要加载的组件类
            component_name: 组件名称（唯一标识）
            placeholder_widget: 加载期间显示的占位符
            parent_widget: 父控件（用于替换占位符）
            init_args: 组件初始化位置参数
            init_kwargs: 组件初始化关键字参数
            callback: 加载完成回调 function(widget, name)
        
        Returns:
            任务ID
        """
        with QMutexLocker(self._mutex):
            if component_name in self._loaded_components:
                self.logger.debug(f"组件已加载: {component_name}")
                if callback:
                    callback(self._loaded_components[component_name], component_name)
                return component_name
            
            if component_name in self._loading_components:
                self.logger.debug(f"组件正在加载: {component_name}")
                return component_name
        
        task_id = f"{component_name}_{int(time.time()*1000)}"
        self.loading_started.emit(component_name)
        
        if placeholder_widget and parent_widget:
            self._placeholders[component_name] = placeholder_widget
        
        worker = UILoaderWorker(component_class, component_name, init_args, init_kwargs or {})
        worker.component_loaded.connect(
            lambda widget, name: self._on_component_loaded(widget, name, callback, parent_widget)
        )
        worker.load_error.connect(self._on_component_error)
        
        with QMutexLocker(self._mutex):
            self._pending_loads.append((task_id, component_name, worker))
        
        self.logger.info(f"UI组件加载任务已加入队列: {component_name}")
        return task_id

    def preload_components(self, component_configs: list):
        """
        预加载多个组件
        
        Args:
            component_configs: 组件配置列表
                [
                    {
                        'class': ComponentClass,
                        'name': 'component_name',
                        'args': (),
                        'kwargs': {},
                        'priority': 0
                    }
                ]
        """
        sorted_configs = sorted(component_configs, key=lambda x: x.get('priority', 0))
        
        for config in sorted_configs:
            self.load_component_async(
                component_class=config['class'],
                component_name=config['name'],
                init_args=config.get('args', ()),
                init_kwargs=config.get('kwargs', {})
            )

    def _process_load_queue(self):
        if not self._pending_loads:
            return
        
        with QMutexLocker(self._mutex):
            running_count = len(self._loading_components)
            if running_count >= self._max_concurrent_loads:
                return
            
            available_slots = self._max_concurrent_loads - running_count
            
            for _ in range(min(available_slots, len(self._pending_loads))):
                task_id, component_name, worker = self._pending_loads.popleft()
                self._loading_components[component_name] = worker
                worker.start()

    def _on_component_loaded(self, widget: QWidget, component_name: str, 
                            callback: Optional[Callable], parent_widget: Optional[QWidget]):
        """组件加载完成（在主线程中执行）"""
        self._loaded_components[component_name] = widget
        
        if component_name in self._loading_components:
            del self._loading_components[component_name]
        
        if component_name in self._placeholders:
            placeholder = self._placeholders[component_name]
            if placeholder and parent_widget:
                self._replace_widget(parent_widget, placeholder, widget)
            del self._placeholders[component_name]
        
        self.component_ready.emit(widget, component_name)
        
        if callback:
            try:
                callback(widget, component_name)
            except Exception as e:
                self.logger.error(f"组件加载回调执行失败: {e}")
        
        self.logger.info(f"✅ UI组件已就绪: {component_name}")

    def _on_component_error(self, component_name: str, error: str):
        """组件加载失败"""
        if component_name in self._loading_components:
            del self._loading_components[component_name]
        
        self.component_failed.emit(component_name, error)
        self.logger.error(f"❌ UI组件加载失败: {component_name}, 错误: {error}")

    @staticmethod
    def _replace_widget(parent: QWidget, old_widget: QWidget, new_widget: QWidget):
        """安全替换控件"""
        layout = parent.layout()
        if not layout:
            return
        
        index = layout.indexOf(old_widget)
        if index >= 0:
            layout.removeWidget(old_widget)
            old_widget.hide()
            old_widget.deleteLater()
            layout.insertWidget(index, new_widget)
            new_widget.show()

    def get_loaded_component(self, component_name: str) -> Optional[QWidget]:
        """获取已加载的组件"""
        return self._loaded_components.get(component_name)

    def is_component_loaded(self, component_name: str) -> bool:
        """检查组件是否已加载"""
        return component_name in self._loaded_components

    def is_component_loading(self, component_name: str) -> bool:
        """检查组件是否正在加载"""
        return component_name in self._loading_components

    def get_loading_status(self) -> Dict[str, Any]:
        """获取加载状态"""
        return {
            'loaded': list(self._loaded_components.keys()),
            'loading': list(self._loading_components.keys()),
            'pending': len(self._pending_loads)
        }

    def shutdown(self):
        """关闭加载器"""
        self._process_timer.stop()
        
        with QMutexLocker(self._mutex):
            for _, _, worker in self._pending_loads:
                worker.wait(1000)
            for worker in self._loading_components.values():
                worker.wait(1000)
        
        self._pending_loads.clear()
        self._loading_components.clear()
        self.logger.info("异步UI加载器已关闭")


_loader_instance: Optional[AsyncUILoader] = None

def get_ui_loader() -> AsyncUILoader:
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = AsyncUILoader()
    return _loader_instance

def reset_ui_loader():
    global _loader_instance
    if _loader_instance:
        _loader_instance.shutdown()
        _loader_instance = None
