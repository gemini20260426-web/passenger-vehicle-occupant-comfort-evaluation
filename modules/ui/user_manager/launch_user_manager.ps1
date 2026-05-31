# 用户管理启动器 - PowerShell版本
param(
    [switch]$Help
)

if ($Help) {
    Write-Host "用户管理启动器" -ForegroundColor Cyan
    Write-Host "用法: .\launch_user_manager.ps1" -ForegroundColor White
    Write-Host "参数:" -ForegroundColor White
    Write-Host "  -Help    显示此帮助信息" -ForegroundColor White
    exit 0
}

# 设置控制台编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Green
Write-Host "           用户管理启动器" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# 检查Python是否安装
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Python已安装: $pythonVersion" -ForegroundColor Green
    } else {
        throw "Python未找到"
    }
} catch {
    Write-Host "✗ 错误: 未找到Python，请先安装Python" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# 检查PySide6是否安装
try {
    python -c "import PySide6" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ PySide6已安装" -ForegroundColor Green
        Write-Host "✓ PySide6已安装" -ForegroundColor Green
    } else {
        throw "PySide6未找到"
    }
} catch {
    Write-Host "✗ 错误: 未找到PySide6，请先安装PySide6" -ForegroundColor Red
    Write-Host "安装命令: pip install PySide6" -ForegroundColor Yellow
    Read-Host "按回车键退出"
    exit 1
}

# 设置项目根目录
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Get-Item $scriptDir).Parent.Parent.Parent.FullName

# 切换到脚本目录
Set-Location $scriptDir

Write-Host "正在启动用户管理..." -ForegroundColor Cyan
Write-Host "项目根目录: $projectRoot" -ForegroundColor Yellow
Write-Host ""

# 运行Python脚本
try {
    python launch_user_manager.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "程序运行出错，请检查错误信息" -ForegroundColor Red
        Read-Host "按回车键退出"
    }
} catch {
    Write-Host ""
    Write-Host "运行出错: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "按回车键退出"
}
