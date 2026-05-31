@echo off
chcp 65001 >nul
echo ========================================
echo       Python脚本路径修复测试
echo ========================================
echo.

echo 🔍 测试Python脚本内部的路径计算...
echo.

echo 📋 测试1: 显示Python脚本计算的项目根目录
python "%~dp0system_backup.py" --action list
echo.

echo 📋 测试2: 检查Python脚本是否正确识别项目结构
echo 如果路径正确，应该看到更多文件被扫描
echo.

echo 📋 测试3: 验证备份目录位置
if exist "%~dp0..\..\backups" (
    echo ✅ 备份目录在正确位置: %~dp0..\..\backups
    dir "%~dp0..\..\backups" /b
) else (
    echo ❌ 备份目录位置错误
)

echo.
echo 📋 测试4: 验证配置文件位置
if exist "%~dp0..\..\backup_config.json" (
    echo ✅ 配置文件在正确位置: %~dp0..\..\backup_config.json
) else (
    echo ❌ 配置文件位置错误
)

echo.
echo ========================================
echo           测试完成
echo ========================================
echo.
echo 💡 如果路径正确，现在运行备份应该扫描到更多文件
echo.
pause
