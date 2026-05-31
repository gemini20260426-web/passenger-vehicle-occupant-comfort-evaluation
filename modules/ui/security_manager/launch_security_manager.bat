@echo off
chcp 65001 >nul
title 系统安全管理启动器

echo ========================================
echo           系统安全管理启动器
echo ========================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python
    pause
    exit /b 1
)

:: 检查PySide6是否安装
python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到PySide6，请先安装PySide6
    echo 安装命令: pip install PySide6
    pause
    exit /b 1
)

:: 设置项目根目录
set PROJECT_ROOT=%~dp0..\..\..\

:: 切换到脚本目录
cd /d "%~dp0"

echo 正在启动系统安全管理...
echo 项目根目录: %PROJECT_ROOT%
echo.

:: 运行Python脚本
python launch_security_manager.py

if errorlevel 1 (
    echo.
    echo 程序运行出错，请检查错误信息
    pause
)
