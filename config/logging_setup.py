#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统日志配置模块（统一版 v2.0）
提供唯一入口配置所有日志，所有模块通过 get_logger(__name__) 自动继承

特性:
  - 日志目录: 项目根/logs/ (绝对路径，不受 CWD 影响)
  - 3 个日志文件: app.log / error.log / debug.log
  - 自动总大小检查 (默认 200MB)
  - SafeRotatingFileHandler: 文件占用时优雅降级
  - 统一工厂函数 get_logger(name)
"""

import os
import sys
import logging
import logging.handlers
import io
import time
from pathlib import Path
from typing import Optional


_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """安全的日志滚动处理器，文件被占用时跳过滚动"""

    def doRollover(self):
        try:
            if hasattr(self.stream, 'fileno'):
                self.stream.close()
                logging.handlers.RotatingFileHandler.doRollover(self)
                self.stream = self._open()
        except PermissionError:
            if self.stream and not self.stream.closed:
                try:
                    self.stream.flush()
                except Exception:
                    pass
            logging.getLogger(__name__).warning(
                f"日志文件 {self.baseFilename} 被其他进程占用，跳过滚动"
            )
        except Exception as e:
            logging.getLogger(__name__).error(f"日志滚动失败: {e}")


def _fix_stdio_encoding():
    """修复 Windows 下的 UTF-8 编码"""
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
        except io.UnsupportedOperation:
            pass
    if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
        try:
            sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)
        except io.UnsupportedOperation:
            pass


def check_log_size(log_dir=None, max_total_mb=200):
    """检查日志目录总大小，超过上限时删除最旧的备份文件"""
    if log_dir is None:
        log_dir = _PROJECT_ROOT / "logs"
    log_path = Path(log_dir)
    if not log_path.exists():
        return

    total_size = sum(f.stat().st_size for f in log_path.glob("*") if f.is_file())
    total_mb = total_size / (1024 * 1024)

    if total_mb > max_total_mb:
        logger = logging.getLogger(__name__)
        logger.warning(f"日志目录总大小 {total_mb:.1f}MB 超过上限 {max_total_mb}MB，开始清理...")

        files = sorted(
            log_path.glob("*"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        current_logs = {"app.log", "error.log", "debug.log"}
        for f in files:
            if f.name in current_logs:
                continue
            size_mb = f.stat().st_size / (1024 * 1024)
            try:
                f.unlink()
                logger.info(f"  已删除旧日志: {f.name} ({size_mb:.1f}MB)")
            except Exception:
                pass

            total_size = sum(f.stat().st_size for f in log_path.glob("*") if f.is_file())
            if total_size / (1024 * 1024) <= max_total_mb * 0.7:
                break


def setup_system_logging(
    log_level: str = "INFO",
    log_dir: Optional[str] = None,
    enable_console: bool = True,
    enable_file: bool = True
) -> logging.Logger:
    """
    设置系统日志配置（全系统唯一调用点）

    Args:
        log_level: 日志级别
        log_dir: 日志目录，None 时自动使用 <项目根>/logs/
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出

    Returns:
        配置好的根日志记录器
    """
    _fix_stdio_encoding()

    if log_dir is None:
        log_dir = _PROJECT_ROOT / "logs"
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True, parents=True)

    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(level)

    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    detail_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n'
        '文件: %(pathname)s:%(lineno)d\n'
        '函数: %(funcName)s\n',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    debug_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n'
        '文件: %(pathname)s:%(lineno)d\n',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    if enable_file:
        app_handler = SafeRotatingFileHandler(
            log_path / "app.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        app_handler.setLevel(logging.INFO)
        app_handler.setFormatter(file_formatter)
        root_logger.addHandler(app_handler)

        error_handler = SafeRotatingFileHandler(
            log_path / "error.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detail_formatter)
        root_logger.addHandler(error_handler)

        debug_handler = SafeRotatingFileHandler(
            log_path / "debug.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8'
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(debug_formatter)
        root_logger.addHandler(debug_handler)

    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    root_logger.info("=" * 60)
    root_logger.info("日志系统初始化完成")
    root_logger.info(f"  日志目录: {log_path.absolute()}")
    root_logger.info(f"  日志级别: {log_level.upper()}")
    root_logger.info(f"  文件输出: {'启用' if enable_file else '禁用'}")
    root_logger.info(f"  控制台输出: {'启用' if enable_console else '禁用'}")
    root_logger.info("=" * 60)

    check_log_size(log_dir)

    return root_logger


def get_logger(name: str = None) -> logging.Logger:
    """
    获取日志记录器（统一工厂函数）
    所有模块应通过此函数获取 logger，确保继承根配置

    Args:
        name: 模块名，None 时自动推断调用者模块名

    Returns:
        配置好的日志记录器
    """
    if name is None:
        import inspect
        frame = inspect.currentframe()
        try:
            while frame:
                frame = frame.f_back
                if frame and frame.f_globals.get('__name__') != __name__:
                    name = frame.f_globals.get('__name__', 'unknown')
                    break
        finally:
            del frame

    return logging.getLogger(name)


def log_system_startup():
    """记录系统启动日志"""
    logger = get_logger(__name__)
    logger.info("=" * 60)
    logger.info("Core UI 系统启动")
    logger.info(f"  Python: {sys.version}")
    logger.info(f"  项目根: {_PROJECT_ROOT}")
    logger.info("=" * 60)


def log_system_shutdown():
    """记录系统关闭日志"""
    logger = get_logger(__name__)
    logger.info("=" * 60)
    logger.info("Core UI 系统关闭")
    logger.info("=" * 60)
