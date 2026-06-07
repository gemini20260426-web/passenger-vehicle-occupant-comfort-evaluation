#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 历史版本备注: py
# 状态: 【当前使用 ACTIVE】- 主程序入口
# 调用链: 本文件 -> core_ui_controller.py -> modules/ui/core_ui_refactored/
# ============================================================
"""
Core System Dashboard - 主程序入口
重构版本：使用水平关系架构

作者: Core System Technologies
版本: 2.0.0
重构日期: 2025-08-15
"""

import sys
import os
import ctypes
import warnings

sys.setrecursionlimit(5000)

# 抑制 matplotlib tight_layout 兼容性警告 (非功能性, 不影响图表渲染)
warnings.filterwarnings('ignore', message='.*tight_layout.*')
warnings.filterwarnings('ignore', message='.*Axes that are not compatible with tight_layout.*')

# ============================================================
# 第一层：修复 Windows 控制台编码 (必须最先执行)
# PowerShell 默认 GBK 导致 UTF-8 日志全部乱码
# SetConsoleOutputCP(65001) = UTF-8 代码页
# ============================================================
_cts_kernel32 = ctypes.windll.kernel32
_cts_kernel32.SetConsoleOutputCP(65001)
_cts_kernel32.SetConsoleCP(65001)

# ============================================================
# 第二层：阻止 Qt 加载搜狗输入法 IME 插件
# os.environ 设置 Python 层 + os.putenv 设置 C 语言层
# + ctypes SetEnvironmentVariableW 调用 Win32 API 直接设置
# 三重保障确保 PySide6/Qt 的 C 扩展不触及受限 DLL
# ============================================================
for _key, _val in [
    ('QT_IM_MODULE', 'none'),
    ('QT_QPA_PLATFORM', 'windows'),
]:
    os.environ[_key] = _val
    try:
        os.putenv(_key, _val)
    except Exception:
        pass
    try:
        ctypes.windll.kernel32.SetEnvironmentVariableW(_key, _val)
    except Exception:
        pass

# 修复 Python 层 stdout/stderr 编码
for _stream in (sys.stdout, sys.stderr):
    try:
        if hasattr(_stream, 'reconfigure'):
            _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import logging
import gc
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ============================================================
# 全局禁用手动 gc.collect()
# 原因：gc.collect() 是 stop-the-world 操作，持有 GIL 全局锁，
# 在主线程或任何线程调用都会冻结整个 Python 解释器和 Qt UI。
# Python 的引用计数 + 自动分代 GC 已完全足够管理内存，
# 手动触发 GC 在 93% 内存使用率下只会浪费 CPU 并导致 UI 卡死。
# 项目中有 23 个 gc.collect() 调用点，通过 monkey-patch 统一覆盖。
# ============================================================
_gc_collect_original = gc.collect
gc.collect = lambda *args, **kwargs: 0
_gc_collect_neutered = True

# 导入日志配置模块
try:
    from config.logging_setup import setup_system_logging, get_logger, log_system_startup
    setup_system_logging(log_level="INFO", enable_console=True, enable_file=True)
    logger = get_logger(__name__)
    log_system_startup()
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.warning("日志配置模块不可用，使用基本日志配置")

def main():
    """主程序入口"""
    try:
        print("Core System Dashboard v2.0.0 启动中...")
        print("架构: 重构后的水平关系架构")
        print("=" * 60)
        
        # 检查Python版本
        if sys.version_info < (3, 8):
            print("[FAIL] 错误: 需要Python 3.8或更高版本")
            print(f"   当前版本: {sys.version}")
            return 1
        
        # 检查依赖项
        if not _check_dependencies():
            return 1
        
        # 导入并启动重构后的主控制器
        from main.core_ui_controller import CoreUIController
        
        # 创建QApplication实例
        from PySide6.QtWidgets import QApplication
        app = QApplication(sys.argv)
        app.setApplicationName("Core System Dashboard v2.0.0")
        app.setApplicationVersion("2.0.0")
        app.setOrganizationName("Core System Technologies")
        app.setQuitOnLastWindowClosed(True)

        # 创建并显示主控制器
        controller = CoreUIController()

        from core.core.service_locator import ServiceLocator
        ServiceLocator().register('core_ui_controller', controller)
        
        # 显示启动信息
        exit_code = controller.start_ui(app)
        return exit_code
            
    except ImportError as e:
        print(f"[FAIL] 导入错误: {e}")
        print("请检查依赖项是否正确安装")
        return 1
    except Exception as e:
        print(f"[FAIL] 启动失败: {e}")
        logger.error(f"主程序启动失败: {e}", exc_info=True)
        return 1

def _check_dependencies():
    """检查必要的依赖项"""
    required_packages = [
        'PySide6',
        'matplotlib',
        'numpy'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'PySide6':
                import PySide6
            elif package == 'matplotlib':
                import matplotlib
            elif package == 'numpy':
                import numpy
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("[FAIL] 缺少必要的依赖包:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n请使用以下命令安装:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    print("[OK] 所有依赖项检查通过")
    return True

if __name__ == "__main__":
    sys.exit(main())

