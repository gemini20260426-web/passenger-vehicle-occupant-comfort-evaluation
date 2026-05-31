@echo off
chcp 65001 >nul
echo ========================================
echo           路径修复验证脚本
echo ========================================
echo.

echo 🔍 当前脚本目录: %~dp0
echo 🔍 当前工作目录: %CD%
echo.

echo 🔍 测试路径计算...
set PROJECT_ROOT=%~dp0..\..
echo 🔍 计算的项目根目录: %PROJECT_ROOT%
echo.

echo 🔍 切换到项目根目录...
cd /d "%PROJECT_ROOT%"
echo 🔍 切换后工作目录: %CD%
echo.

echo 🔍 验证目录内容...
echo 应该看到以下关键目录:
dir /b | findstr /i "core modules tools main data"
echo.

echo 🔍 检查Python脚本路径...
if exist "tools\backup_tools\system_backup.py" (
    echo ✅ Python脚本路径正确
    echo 📁 路径: tools\backup_tools\system_backup.py
) else (
    echo ❌ Python脚本路径错误
)

echo.
echo 🔍 检查项目结构...
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

echo.
echo ========================================
echo           验证结果
echo ========================================
echo.
if exist "core" if exist "modules" (
    echo 🎉 路径修复成功！项目根目录设置正确
    echo 📁 现在可以备份整个项目了
) else (
    echo ❌ 路径仍有问题，需要进一步检查
)
echo.
pause
