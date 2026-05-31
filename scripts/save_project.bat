@echo off
REM 项目保存批处理脚本

echo 正在保存项目文件...
echo.

REM 检查Python是否可用
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Python解释器
    echo 请确保Python已安装并添加到系统PATH中
    pause
    exit /b 1
)

REM 运行Python保存脚本
python "%~dp0save_project.py" %*

if %errorlevel% equ 0 (
    echo.
    echo 项目保存成功!
) else (
    echo.
    echo 项目保存失败!
    pause
    exit /b 1
)

pause