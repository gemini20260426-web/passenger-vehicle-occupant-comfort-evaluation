#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一异步任务调度器 - 全异步架构核心组件
整合QThread、QTimer、asyncio、ThreadPoolExecutor，提供统一的异步任务管理
"""

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any, Optional, Dict, List, Coroutine
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import (
    QObject, Signal, QTimer, QThread, QCoreApplication,
    QThreadPool, QRunnable, QMutex, QMutexLocker
)


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    elapsed_time: float = 0.0


class AsyncTask(QObject):
    """异步任务封装"""
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(float)

    def __init__(self, task_id: str, func: Callable, *args, priority: TaskPriority = TaskPriority.NORMAL, **kwargs):
        super().__init__()
        self.task_id = task_id
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.priority = priority
        self.start_time = None
        self._cancelled = False


class QtAsyncioEventLoop(QObject):
    """基于QTimer的asyncio事件循环，在Qt主线程中运行协程
    
    注意：此组件会显著影响UI性能，仅在确实需要asyncio协程时才启用。
    默认禁用，通过 enable() 方法手动启用。
    """
    def __init__(self):
        super().__init__()
        self._loop = None
        self._timer = QTimer()
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._loop = asyncio.new_event_loop()
        self._timer.start()

    def stop(self):
        self._running = False
        self._timer.stop()
        if self._loop:
            self._loop.close()
            self._loop = None

    def _tick(self):
        if self._loop and self._running:
            try:
                self._loop.run_until_complete(asyncio.sleep(0))
            except Exception:
                pass

    def create_task(self, coro: Coroutine) -> asyncio.Task:
        if not self._loop:
            self._loop = asyncio.new_event_loop()
        return self._loop.create_task(coro)

    def run_coroutine_threadsafe(self, coro: Coroutine) -> asyncio.Future:
        if not self._loop:
            self._loop = asyncio.new_event_loop()
        return asyncio.run_coroutine_threadsafe(coro, self._loop)


class AsyncTaskScheduler(QObject):
    """
    统一异步任务调度器
    
    功能：
    1. 支持协程（asyncio）异步任务
    2. 支持线程池（ThreadPoolExecutor）后台任务
    3. 支持Qt信号槽事件驱动
    4. 任务优先级队列
    5. 任务生命周期管理
    """
    task_started = Signal(str)
    task_completed = Signal(object)
    task_failed = Signal(str, str)
    task_progress = Signal(str, float)
    all_tasks_completed = Signal()

    def __init__(self, max_workers: int = 4, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        
        self._mutex = QMutex()
        self._task_counter = 0
        self._pending_tasks: deque = deque()
        self._running_tasks: Dict[str, AsyncTask] = {}
        self._completed_tasks: Dict[str, TaskResult] = {}
        
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="AsyncScheduler"
        )
        
        self._qt_event_loop = QtAsyncioEventLoop()
        
        self._process_timer = QTimer(self)
        self._process_timer.timeout.connect(self._process_queue)
        self._process_timer.start(100)
        
        self._max_concurrent_tasks = max_workers
        self._is_shutting_down = False
        
        self.logger.info(f"异步任务调度器已初始化，最大工作线程: {max_workers}")

    def generate_task_id(self, prefix: str = "task") -> str:
        with QMutexLocker(self._mutex):
            self._task_counter += 1
            return f"{prefix}_{self._task_counter}_{int(time.time()*1000)}"

    def submit(self, func: Callable, *args, priority: TaskPriority = TaskPriority.NORMAL, 
               task_id: Optional[str] = None, **kwargs) -> str:
        if self._is_shutting_down:
            self.logger.warning("调度器正在关闭，拒绝新任务")
            return ""
        
        tid = task_id or self.generate_task_id(func.__name__)
        task = AsyncTask(tid, func, *args, priority=priority, **kwargs)
        
        with QMutexLocker(self._mutex):
            self._pending_tasks.append(task)
        
        self.logger.debug(f"任务已提交: {tid}, 优先级: {priority.name}")
        return tid

    def submit_coroutine(self, coro: Coroutine, task_id: Optional[str] = None,
                        priority: TaskPriority = TaskPriority.NORMAL) -> str:
        if self._is_shutting_down:
            self.logger.warning("调度器正在关闭，拒绝新任务")
            return ""
        
        tid = task_id or self.generate_task_id("coroutine")
        
        async def _run_with_tracking():
            start = time.time()
            self.task_started.emit(tid)
            try:
                result = await coro
                elapsed = time.time() - start
                task_result = TaskResult(tid, True, result, elapsed_time=elapsed)
                self._completed_tasks[tid] = task_result
                self.task_completed.emit(task_result)
                return result
            except Exception as e:
                elapsed = time.time() - start
                self.task_failed.emit(tid, str(e))
                return None
        
        self._qt_event_loop.create_task(_run_with_tracking())
        return tid

    def submit_to_thread_pool(self, func: Callable, *args, priority: TaskPriority = TaskPriority.NORMAL,
                             task_id: Optional[str] = None, callback: Optional[Callable] = None,
                             error_callback: Optional[Callable] = None, **kwargs) -> str:
        if self._is_shutting_down:
            self.logger.warning("调度器正在关闭，拒绝新任务")
            return ""
        
        tid = task_id or self.generate_task_id(func.__name__)
        self.task_started.emit(tid)
        
        def _wrapper():
            start = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                task_result = TaskResult(tid, True, result, elapsed_time=elapsed)
                self._completed_tasks[tid] = task_result
                
                QCoreApplication.instance().postEvent(
                    self, _TaskCompletedEvent(tid, task_result)
                )
                
                if callback:
                    QCoreApplication.instance().postEvent(
                        self, _CallbackEvent(callback, result)
                    )
            except Exception as e:
                elapsed = time.time() - start
                task_result = TaskResult(tid, False, None, str(e), elapsed_time=elapsed)
                self._completed_tasks[tid] = task_result
                
                QCoreApplication.instance().postEvent(
                    self, _TaskFailedEvent(tid, str(e))
                )
                
                if error_callback:
                    QCoreApplication.instance().postEvent(
                        self, _CallbackEvent(error_callback, e)
                    )
        
        self._executor.submit(_wrapper)
        return tid

    def _process_queue(self):
        if self._is_shutting_down:
            return
        
        with QMutexLocker(self._mutex):
            if not self._pending_tasks:
                return
            
            running_count = len(self._running_tasks)
            if running_count >= self._max_concurrent_tasks:
                return
            
            available_slots = self._max_concurrent_tasks - running_count
            
            for _ in range(min(available_slots, len(self._pending_tasks))):
                task = self._pending_tasks.popleft()
                self._running_tasks[task.task_id] = task
                self._execute_task(task)

    def _execute_task(self, task: AsyncTask):
        def _wrapper():
            start = time.time()
            self.task_started.emit(task.task_id)
            try:
                result = task.func(*task.args, **task.kwargs)
                elapsed = time.time() - start
                task_result = TaskResult(task.task_id, True, result, elapsed_time=elapsed)
                self._completed_tasks[task.task_id] = task_result
                
                QCoreApplication.instance().postEvent(
                    self, _TaskCompletedEvent(task.task_id, task_result)
                )
            except Exception as e:
                elapsed = time.time() - start
                self.task_failed.emit(task.task_id, str(e))
                task_result = TaskResult(task.task_id, False, None, str(e), elapsed_time=elapsed)
                self._completed_tasks[task.task_id] = task_result
                
                QCoreApplication.instance().postEvent(
                    self, _TaskFailedEvent(task.task_id, str(e))
                )
            finally:
                with QMutexLocker(self._mutex):
                    self._running_tasks.pop(task.task_id, None)
        
        self._executor.submit(_wrapper)

    def customEvent(self, event):
        if isinstance(event, _TaskCompletedEvent):
            self.task_completed.emit(event.result)
        elif isinstance(event, _TaskFailedEvent):
            self.task_failed.emit(event.task_id, event.error)
        elif isinstance(event, _CallbackEvent):
            try:
                event.callback(*event.args, **event.kwargs)
            except Exception as e:
                self.logger.error(f"回调执行失败: {e}")

    def cancel_task(self, task_id: str) -> bool:
        with QMutexLocker(self._mutex):
            for i, task in enumerate(self._pending_tasks):
                if task.task_id == task_id:
                    self._pending_tasks.remove(task)
                    return True
        return False

    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        return self._completed_tasks.get(task_id)

    def get_pending_count(self) -> int:
        with QMutexLocker(self._mutex):
            return len(self._pending_tasks)

    def get_running_count(self) -> int:
        with QMutexLocker(self._mutex):
            return len(self._running_tasks)

    def shutdown(self, wait: bool = True):
        self._is_shutting_down = True
        self._process_timer.stop()
        self._qt_event_loop.stop()
        
        if wait:
            self._executor.shutdown(wait=True)
        else:
            self._executor.shutdown(wait=False)
        
        self.logger.info("异步任务调度器已关闭")


class _TaskCompletedEvent:
    def __init__(self, task_id: str, result: TaskResult):
        self.task_id = task_id
        self.result = result
        self.type = QCoreApplication.registerEventType()


class _TaskFailedEvent:
    def __init__(self, task_id: str, error: str):
        self.task_id = task_id
        self.error = error
        self.type = QCoreApplication.registerEventType()


class _CallbackEvent:
    def __init__(self, callback: Callable, *args, **kwargs):
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self.type = QCoreApplication.registerEventType()


_scheduler_instance: Optional[AsyncTaskScheduler] = None

def get_scheduler(max_workers: int = 4) -> AsyncTaskScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = AsyncTaskScheduler(max_workers=max_workers)
    return _scheduler_instance

def reset_scheduler():
    global _scheduler_instance
    if _scheduler_instance:
        _scheduler_instance.shutdown(wait=False)
        _scheduler_instance = None
