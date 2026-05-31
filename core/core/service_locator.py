#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
轻量级服务定位器 (Service Locator)
替代循环导入和 try/except ImportError 的脆弱模式
提供全局服务注册与查找，消除模块间硬依赖
"""

import logging
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ServiceLocator:
    """全局服务注册与查找 — 线程安全的单例"""

    _instance: Optional['ServiceLocator'] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> 'ServiceLocator':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._services = {}
        return cls._instance

    def register(self, name: str, service: Any) -> None:
        if name in self._services:
            logger.debug("服务覆盖注册: %s", name)
        self._services[name] = service
        logger.debug("服务已注册: %s (type=%s)", name, type(service).__name__)

    def get(self, name: str, default: Any = None) -> Optional[Any]:
        service = self._services.get(name, default)
        if service is None and default is None:
            logger.debug("服务未找到: %s", name)
        return service

    def has(self, name: str) -> bool:
        return name in self._services

    def unregister(self, name: str) -> None:
        self._services.pop(name, None)
        logger.debug("服务已注销: %s", name)

    def clear(self) -> None:
        self._services.clear()
        logger.debug("所有服务已清除")

    def list_services(self) -> Dict[str, str]:
        return {k: type(v).__name__ for k, v in self._services.items()}
