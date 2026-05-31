@echo off
chcp 65001 >nul
echo ========================================
echo           备份工具测试脚本
echo ========================================
echo.

echo 🔍 测试Python脚本路径...
if exist "%~dp0system_backup.py" (
    echo ✅ 找到system_backup.py文件
) else (
    echo ❌ 未找到system_backup.py文件
    pause
    exit /b 1
)

echo.
echo 🔍 测试Python脚本执行...
python "%~dp0system_backup.py" --help
if errorlevel 1 (
    echo ❌ Python脚本执行失败
) else (
    echo ✅ Python脚本执行成功
)

echo.
echo 🔍 测试备份列表功能...
python "%~dp0system_backup.py" --action list

echo.
echo ✅ 测试完成！
pause
