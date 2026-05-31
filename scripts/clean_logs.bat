@echo off
chcp 65001 >nul
echo 日志清理工具
echo ================

echo.
echo 选择操作:
echo 1. 检查日志文件大小
echo 2. 轮转日志文件
echo 3. 压缩日志文件
echo 4. 清理旧备份
echo 5. 自动管理
echo 6. 退出

set /p choice=请输入选择 (1-6): 

if "%choice%"=="1" (
    echo 检查日志文件大小...
    python scripts\log_manager.py --check
) else if "%choice%"=="2" (
    echo 轮转日志文件...
    python scripts\log_manager.py --rotate
) else if "%choice%"=="3" (
    echo 压缩日志文件...
    python scripts\log_manager.py --compress
) else if "%choice%"=="4" (
    echo 清理旧备份...
    python scripts\log_manager.py --clean
) else if "%choice%"=="5" (
    echo 自动管理日志...
    python scripts\log_manager.py --auto
) else if "%choice%"=="6" (
    echo 退出...
    exit /b 0
) else (
    echo 无效选择，执行自动管理...
    python scripts\log_manager.py --auto
)

echo.
echo 操作完成，按任意键退出...
pause >nul



