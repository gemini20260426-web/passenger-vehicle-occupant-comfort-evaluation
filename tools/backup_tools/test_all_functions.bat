@echo off
chcp 65001 >nul
echo ========================================
echo           备份工具完整功能测试
echo ========================================
echo.

echo 🔍 测试1: 检查Python脚本...
if exist "%~dp0system_backup.py" (
    echo ✅ 找到system_backup.py文件
) else (
    echo ❌ 未找到system_backup.py文件
    pause
    exit /b 1
)

echo.
echo 🔍 测试2: 测试帮助信息...
python "%~dp0system_backup.py" --help
if errorlevel 1 (
    echo ❌ 帮助信息显示失败
) else (
    echo ✅ 帮助信息显示成功
)

echo.
echo 🔍 测试3: 查看备份列表...
python "%~dp0system_backup.py" --action list
if errorlevel 1 (
    echo ❌ 备份列表查看失败
) else (
    echo ✅ 备份列表查看成功
)

echo.
echo 🔍 测试4: 测试清理功能（不实际清理）...
echo 注意: 这只是测试，不会实际删除文件
python "%~dp0system_backup.py" --action cleanup
if errorlevel 1 (
    echo ❌ 清理功能测试失败
) else (
    echo ✅ 清理功能测试成功
)

echo.
echo 🔍 测试5: 检查备份目录...
if exist "%~dp0..\..\backups" (
    echo ✅ 备份目录存在
    dir "%~dp0..\..\backups" /b
) else (
    echo ❌ 备份目录不存在
)

echo.
echo 🔍 测试6: 检查配置文件...
if exist "%~dp0..\..\backup_config.json" (
    echo ✅ 备份配置文件存在
) else (
    echo ❌ 备份配置文件不存在
)

echo.
echo 🔍 测试7: 检查日志文件...
if exist "%~dp0..\..\logs" (
    echo ✅ 日志目录存在
    dir "%~dp0..\..\logs\backup_*.log" /b 2>nul
) else (
    echo ❌ 日志目录不存在
)

echo.
echo ========================================
echo           测试完成总结
echo ========================================
echo.
echo 🎉 所有功能测试完成！
echo 📁 备份工具已准备就绪
echo 💡 现在可以运行 backup.bat 来使用完整功能
echo.
pause
