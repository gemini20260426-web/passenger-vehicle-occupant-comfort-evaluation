# 系统备份工具使用说明

## 概述
这是一个完整的系统备份工具，支持全量备份、备份列表查看和旧备份清理功能。

## 文件说明

### 主要文件
- `system_backup.py` - 核心备份脚本（Python）
- `backup.bat` - Windows批处理启动脚本
- `backup.ps1` - PowerShell启动脚本
- `test_backup.bat` - 测试脚本

### 配置文件
- `backup_config.json` - 备份配置文件（自动生成）

## 使用方法

### 方法1：使用批处理文件（推荐）
```bash
# 双击运行或在命令行中执行
backup.bat
```

### 方法2：使用PowerShell脚本
```powershell
# 在PowerShell中执行
.\backup.ps1
```

### 方法3：直接使用Python脚本
```bash
# 创建备份
python system_backup.py --action backup

# 查看备份列表
python system_backup.py --action list

# 清理旧备份
python system_backup.py --action cleanup

# 查看帮助
python system_backup.py --help
```

## 功能说明

### 1. 创建全量备份
- 自动扫描项目目录
- 排除临时文件和缓存文件
- 创建压缩备份包
- 生成备份清单

### 2. 查看备份列表
- 显示所有备份文件
- 显示备份大小和创建时间
- 显示备份状态

### 3. 清理旧备份
- 根据配置的保留天数自动清理
- 默认保留30天
- 安全删除过期备份

## 配置选项

备份工具会自动创建 `backup_config.json` 配置文件，包含以下选项：

```json
{
    "exclude_patterns": [
        "*.pyc", "__pycache__", "*.log", "*.tmp", "*.cache",
        ".git", ".vscode", "node_modules", "venv", "env"
    ],
    "include_patterns": [
        "*.py", "*.md", "*.txt", "*.json", "*.xml", "*.yaml"
    ],
    "compression": true,
    "encryption": false,
    "retention_days": 30
}
```

## 故障排除

### 常见问题

1. **Python未找到**
   - 确保已安装Python 3.7+
   - 确保Python在系统PATH中

2. **路径错误**
   - 确保在正确的目录中运行脚本
   - 检查文件路径是否正确

3. **权限问题**
   - 确保有足够的权限创建备份目录
   - 以管理员身份运行（如需要）

### 测试工具
运行 `test_backup.bat` 来诊断常见问题。

## 备份位置
备份文件默认保存在项目根目录的 `backups/` 文件夹中。

## 日志文件
备份操作的日志保存在 `logs/backup_YYYYMMDD.log` 文件中。
