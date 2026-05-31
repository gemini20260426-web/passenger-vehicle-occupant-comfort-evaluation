# UI重构项目备份工具使用说明

## 🎯 功能概述

这是一个专门为UI重构项目设计的备份工具，可以将整个项目目录备份到E盘根目录，支持压缩、增量备份、时间戳命名等功能。

## 📁 备份位置

- **备份目标**: `E:\UI重构备份\`
- **备份格式**: 压缩ZIP包 + 信息JSON文件
- **命名规则**: `UI重构_全量备份_YYYYMMDD_HHMMSS.zip`

## 🚀 使用方法

### 方法1: 双击批处理文件（推荐）
1. 双击 `启动UI重构备份.bat` 文件
2. 等待备份完成
3. 查看E盘中的备份文件

### 方法2: 双击PowerShell脚本
1. 双击 `启动UI重构备份.ps1` 文件
2. 如果出现执行策略错误，请以管理员身份运行PowerShell并执行：
   ```powershell
   Set-ExecutionPolicy RemoteSigned
   ```

### 方法3: 命令行运行
```bash
# 进入备份工具目录
cd tools/backup_tools

# 执行备份
python ui_backup_to_e_drive.py

# 查看备份列表
python ui_backup_to_e_drive.py --action list

# 清理旧备份
python ui_backup_to_e_drive.py --action cleanup
```

## ⚙️ 配置说明

备份工具会自动创建配置文件 `ui_backup_config.json`，包含以下设置：

### 排除模式
- `*.pyc` - Python编译文件
- `__pycache__` - Python缓存目录
- `*.log` - 日志文件
- `*.tmp`, `*.cache` - 临时文件
- `.git`, `.vscode` - 版本控制和IDE文件
- `venv`, `.venv` - 虚拟环境
- `backups/*`, `temp/*`, `logs/*` - 备份和临时目录
- `*.pkl`, `*.zip`, `*.tar.gz` - 数据文件和压缩包

### 包含模式
- `*.py` - Python源代码文件
- `*.md` - Markdown文档
- `*.txt`, `*.json`, `*.xml`, `*.yaml` - 配置文件
- `*.html`, `*.css`, `*.js` - 前端文件
- `*.png`, `*.jpg`, `*.svg` - 图片文件
- `*.bat`, `*.ps1`, `*.sh` - 脚本文件

### 其他设置
- `compression`: 是否启用压缩（默认：是）
- `compression_level`: 压缩级别（默认：6，范围1-9）
- `retention_days`: 备份保留天数（默认：30天）
- `max_backup_size_gb`: 最大备份大小（默认：10GB）

## 📊 备份信息

每次备份完成后，会生成一个 `.info.json` 文件，包含：

```json
{
    "backup_name": "UI重构_全量备份_20250816_105805",
    "backup_time": "20250816_105805",
    "project_root": "D:\\UI重构",
    "total_files": 1234,
    "copied_files": 1200,
    "excluded_files": 34,
    "total_size_bytes": 123456789,
    "total_size_mb": 117.8,
    "compression": true,
    "config": {...}
}
```

## 🔧 高级功能

### 1. 增量备份
工具会自动跳过已存在的相同文件，提高备份效率。

### 2. 智能排除
根据文件类型和路径模式智能排除不需要备份的文件。

### 3. 压缩优化
使用ZIP_DEFLATED算法，平衡压缩率和速度。

### 4. 自动清理
可以设置自动清理超过保留天数的旧备份。

## ⚠️ 注意事项

1. **确保E盘有足够空间** - 建议至少预留项目大小的2倍空间
2. **备份时间** - 首次备份可能需要较长时间，取决于项目大小
3. **网络驱动器** - 如果E盘是网络驱动器，备份速度可能较慢
4. **权限问题** - 确保有E盘的写入权限

## 🆘 故障排除

### 常见问题

1. **Python未找到**
   - 确保Python已安装并添加到PATH环境变量
   - 或者使用完整路径：`C:\Python39\python.exe ui_backup_to_e_drive.py`

2. **权限不足**
   - 以管理员身份运行命令提示符或PowerShell
   - 检查E盘的写入权限

3. **备份失败**
   - 检查日志文件：`logs/ui_backup_e_drive_YYYYMMDD.log`
   - 确保E盘有足够空间

4. **文件被占用**
   - 关闭可能占用文件的程序
   - 重新运行备份脚本

## 📞 技术支持

如果遇到问题，请检查：
1. 日志文件中的错误信息
2. Python版本兼容性
3. 磁盘空间和权限
4. 文件是否被其他程序占用

---

**版本**: 1.0  
**更新日期**: 2025-08-16  
**作者**: AI助手
