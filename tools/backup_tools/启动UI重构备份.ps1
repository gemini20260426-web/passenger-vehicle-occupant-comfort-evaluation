# UI重构项目备份工具 - PowerShell版本
# 备份到E盘根目录

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "    UI重构项目备份工具" -ForegroundColor Yellow
Write-Host "    备份到E盘根目录" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "正在启动备份脚本..." -ForegroundColor Green
Write-Host ""

# 切换到脚本所在目录
Set-Location $PSScriptRoot

# 检查Python是否可用
try {
    $pythonVersion = python --version 2>&1
    Write-Host "检测到Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ 未检测到Python，请确保Python已安装并添加到PATH" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# 运行备份脚本
Write-Host "🚀 开始执行备份..." -ForegroundColor Green
python ui_backup_to_e_drive.py

Write-Host ""
Write-Host "备份操作完成！" -ForegroundColor Green
Write-Host "按回车键退出..." -ForegroundColor Yellow
Read-Host
