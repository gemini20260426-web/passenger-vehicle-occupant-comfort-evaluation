# 配置管理系统启动器 (PowerShell版本)
# 设置控制台编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "           配置管理系统启动器" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查Python是否安装
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python版本: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "错误: 未找到Python，请先安装Python 3.7+" -ForegroundColor Red
    Write-Host "下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "按回车键退出"
    exit 1
}

# 检查PySide6是否安装
try {
    python -c "import PySide6" 2>$null
    Write-Host "PySide6已安装" -ForegroundColor Green
} catch {
    Write-Host "错误: 未找到PySide6，正在安装..." -ForegroundColor Yellow
    try {
        pip install PySide6
        Write-Host "PySide6安装成功" -ForegroundColor Green
    } catch {
        Write-Host "安装PySide6失败，请手动安装: pip install PySide6" -ForegroundColor Red
        Read-Host "按回车键退出"
        exit 1
    }
}

# 设置项目根目录
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Get-Item $scriptDir).Parent.Parent.Parent.FullName

# 切换到脚本目录
Set-Location $scriptDir

Write-Host "正在启动配置管理系统..." -ForegroundColor Green
Write-Host "项目根目录: $projectRoot" -ForegroundColor Gray
Write-Host ""

# 启动配置管理器
try {
    python launch_config_manager.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "配置管理系统已关闭" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "启动失败，退出代码: $LASTEXITCODE" -ForegroundColor Red
    }
} catch {
    Write-Host ""
    Write-Host "启动失败，错误信息: $_" -ForegroundColor Red
}

Read-Host "按回车键退出"
