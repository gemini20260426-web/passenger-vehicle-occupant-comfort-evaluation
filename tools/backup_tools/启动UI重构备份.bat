@echo off
chcp 65001 >nul
title UI重构项目备份工具 - 备份到E盘

echo.
echo ========================================
echo    UI重构项目备份工具
echo    备份到E盘根目录
echo ========================================
echo.

echo 正在启动备份脚本...
echo.

cd /d "%~dp0"
python ui_backup_to_e_drive.py

echo.
echo 备份操作完成！
echo 按任意键退出...
pause >nul
