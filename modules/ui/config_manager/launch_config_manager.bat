@echo off
chcp 65001 >nul
title 配置管理系统启动器

echo ========================================
echo           配置管理系统启动器
echo ========================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.7+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查PySide6是否安装
python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到PySide6，正在安装...
    pip install PySide6
    if errorlevel 1 (
        echo 安装PySide6失败，请手动安装: pip install PySide6
        pause
        exit /b 1
    )
)

:: 设置项目根目录
set PROJECT_ROOT=%~dp0..\..\..\

:: 切换到脚本目录
cd /d "%~dp0"

echo 正在启动配置管理系统...
echo 项目根目录: %PROJECT_ROOT%
echo.

:: 启动配置管理器
python launch_config_manager.py

if errorlevel 1 (
    echo.
    echo 启动失败，请检查错误信息
    pause
) else (
    echo.
    echo 配置管理系统已关闭
)

pause
