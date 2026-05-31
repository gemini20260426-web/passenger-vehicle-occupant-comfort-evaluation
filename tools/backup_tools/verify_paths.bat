@echo off
chcp 65001 >nul
echo ========================================
echo           路径验证脚本
echo ========================================
echo.

echo 🔍 当前脚本目录: %~dp0
echo 🔍 当前工作目录: %CD%
echo.

echo 🔍 计算项目根目录...
set PROJECT_ROOT=%~dp0..\..\..
echo 🔍 项目根目录: %PROJECT_ROOT%
echo.

echo 🔍 切换到项目根目录...
cd /d "%PROJECT_ROOT%"
echo 🔍 切换后工作目录: %CD%
echo.

echo 🔍 验证项目根目录内容...
echo 应该看到以下目录和文件:
dir /b | findstr /i "core modules tools main data"
echo.

echo 🔍 检查关键目录是否存在...
if exist "core" (
    echo ✅ core目录存在
) else (
    echo ❌ core目录不存在
)

if exist "modules" (
    echo ✅ modules目录存在
) else (
    echo ❌ modules目录不存在
)

if exist "main" (
    echo ✅ main目录存在
) else (
    echo ❌ main目录不存在
)

if exist "tools" (
    echo ✅ tools目录存在
) else (
    echo ❌ tools目录不存在
)

echo.
echo 🔍 检查Python脚本路径...
if exist "tools\backup_tools\system_backup.py" (
    echo ✅ Python脚本路径正确: tools\backup_tools\system_backup.py
) else (
    echo ❌ Python脚本路径错误
)

echo.
echo 🔍 检查备份目录位置...
if exist "backups" (
    echo ✅ 备份目录在正确位置: %CD%\backups
) else (
    echo ❌ 备份目录不存在
)

echo.
echo 🔍 检查配置文件位置...
if exist "backup_config.json" (
    echo ✅ 配置文件在正确位置: %CD%\backup_config.json
) else (
    echo ❌ 配置文件不存在
)

echo.
echo ========================================
echo           验证结果
echo ========================================
echo.
if exist "core" if exist "modules" if exist "main" (
    echo 🎉 路径设置正确！现在可以备份整个项目了
) else (
    echo ❌ 路径设置有问题，请检查
)
echo.
pause
