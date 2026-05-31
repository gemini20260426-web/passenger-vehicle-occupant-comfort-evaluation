# 系统部署指南

## 📋 **概述**

本文档详细说明了如何部署重构后的右侧面板系统。该系统完全替代了模拟数据和模拟模型，连接到真实的Core系统，实现了数据同步和任务中断恢复功能。

## 🎯 **系统要求**

### **硬件要求**
- **CPU**: Intel i5 或 AMD Ryzen 5 及以上
- **内存**: 8GB RAM 及以上
- **存储**: 10GB 可用空间
- **网络**: 支持TCP/IP连接

### **软件要求**
- **操作系统**: Windows 10/11, Linux (Ubuntu 18.04+), macOS 10.15+
- **Python**: 3.8 - 3.11
- **Qt**: PySide6 6.0+
- **数据库**: SQLite 3.0+ (内置)

### **依赖库**
```bash
# 核心依赖
PySide6>=6.0.0
numpy>=1.20.0
pandas>=1.3.0

# 可选依赖
psutil>=5.8.0  # 内存监控
matplotlib>=3.5.0  # 数据可视化
```

## 🚀 **安装步骤**

### **步骤1: 环境准备**
```bash
# 创建虚拟环境
python -m venv ui_refactor_env

# 激活虚拟环境
# Windows
ui_refactor_env\Scripts\activate
# Linux/macOS
source ui_refactor_env/bin/activate

# 升级pip
pip install --upgrade pip
```

### **步骤2: 安装依赖**
```bash
# 安装项目依赖
pip install -r requirements.txt

# 或者手动安装核心依赖
pip install PySide6 numpy pandas
```

### **步骤3: 配置系统**
```bash
# 复制配置文件
cp config/config.ini.example config/config.ini
cp config/core_ui_config.json.example config/core_ui_config.json

# 编辑配置文件
# 根据实际环境修改配置参数
```

### **步骤4: 验证安装**
```bash
# 运行基础测试
python test_integration_simple.py

# 运行Qt集成测试
python test_qt_integration.py

# 运行性能测试
python test_performance.py
```

## ⚙️ **配置说明**

### **核心配置文件**

#### **config/config.ini**
```ini
[system]
# 系统基本配置
debug_mode = true
log_level = INFO
max_threads = 8

[database]
# 数据库配置
db_path = data/system.db
backup_interval = 3600

[network]
# 网络配置
timeout = 30
retry_count = 3
```

#### **config/core_ui_config.json**
```json
{
  "ui": {
    "theme": "default",
    "language": "zh_CN",
    "auto_save": true
  },
  "data": {
    "update_interval": 1000,
    "cache_size": 1000,
    "sync_enabled": true
  }
}
```

### **环境变量**
```bash
# 设置环境变量
export UI_DEBUG_MODE=true
export UI_LOG_LEVEL=INFO
export UI_DATA_PATH=/path/to/data
```

## 🔧 **部署选项**

### **选项1: 开发环境部署**
```bash
# 直接运行主程序
python main/main.py

# 或者运行集成版本
python modules/ui/core_ui_main_integration.py
```

### **选项2: 生产环境部署**
```bash
# 创建启动脚本
cat > start_system.sh << 'EOF'
#!/bin/bash
cd /path/to/ui_refactor
source ui_refactor_env/bin/activate
python main/main.py
EOF

chmod +x start_system.sh

# 创建系统服务
sudo cp start_system.sh /usr/local/bin/
sudo systemctl enable ui_refactor
```

### **选项3: Docker部署**
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8080

CMD ["python", "main/main.py"]
```

## 📊 **系统启动**

### **启动顺序**
1. **数据库初始化**: 自动创建必要的表和索引
2. **Core系统连接**: 连接到真实的Core分析系统
3. **UI组件初始化**: 创建左侧控制面板和右侧显示面板
4. **数据同步启动**: 启动数据同步管理器
5. **任务恢复检查**: 检查并恢复中断的任务

### **启动命令**
```bash
# 标准启动
python main/main.py

# 调试模式启动
python -u main/main.py --debug

# 指定配置文件启动
python main/main.py --config /path/to/config.ini
```

## 🔍 **验证部署**

### **功能验证**
1. **左侧控制面板**: 检查所有控制按钮是否正常
2. **右侧显示面板**: 验证所有标签页是否显示
3. **数据同步**: 测试左侧控制与右侧显示的数据同步
4. **模式切换**: 测试重构模式与传统模式的切换

### **性能验证**
1. **响应时间**: 检查UI响应是否流畅
2. **内存使用**: 监控内存使用情况
3. **CPU使用**: 检查CPU占用率
4. **稳定性**: 长时间运行测试

### **日志检查**
```bash
# 查看系统日志
tail -f logs/core_ui_system.log

# 查看错误日志
tail -f logs/error.log

# 查看调试日志
tail -f logs/debug.log
```

## 🚨 **故障排除**

### **常见问题**

#### **问题1: 模块导入失败**
```bash
# 错误信息
ModuleNotFoundError: No module named 'core.multi_source_sync'

# 解决方案
# 检查Core系统路径配置
# 确保Core模块已正确安装
```

#### **问题2: Qt组件创建失败**
```bash
# 错误信息
QGuiApplication::font(): no QGuiApplication instance

# 解决方案
# 确保在Qt应用实例创建后再创建UI组件
```

#### **问题3: 数据同步失败**
```bash
# 错误信息
Data sync failed: connection timeout

# 解决方案
# 检查网络连接
# 验证Core系统状态
# 检查配置文件中的超时设置
```

### **调试模式**
```bash
# 启用详细日志
export UI_LOG_LEVEL=DEBUG

# 启用Qt调试
export QT_LOGGING_RULES="qt.qpa.*=true"

# 运行调试版本
python main/main.py --debug
```

## 📈 **性能调优**

### **系统参数优化**
```ini
[performance]
# 数据更新频率 (毫秒)
update_interval = 500

# 缓存大小
cache_size = 2000

# 线程池大小
max_workers = 16

# 内存限制 (MB)
memory_limit = 2048
```

### **数据库优化**
```sql
-- 创建索引
CREATE INDEX idx_timestamp ON sensor_data(timestamp);
CREATE INDEX idx_data_type ON sensor_data(data_type);

-- 优化查询
ANALYZE sensor_data;
```

## 🔒 **安全配置**

### **访问控制**
```ini
[security]
# 启用用户认证
auth_enabled = true

# 会话超时 (秒)
session_timeout = 3600

# 最大登录尝试
max_login_attempts = 5
```

### **网络安全**
```ini
[network]
# 启用SSL/TLS
ssl_enabled = true
ssl_cert = /path/to/cert.pem
ssl_key = /path/to/key.pem

# 防火墙规则
allowed_ips = 192.168.1.0/24, 10.0.0.0/8
```

## 📋 **维护计划**

### **日常维护**
- 检查系统日志
- 监控系统性能
- 备份重要数据
- 清理临时文件

### **定期维护**
- 每周: 系统性能检查
- 每月: 数据库优化
- 每季度: 安全更新
- 每年: 系统升级

### **备份策略**
```bash
# 自动备份脚本
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/ui_refactor"

# 备份数据库
cp data/system.db "$BACKUP_DIR/system_$DATE.db"

# 备份配置文件
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" config/

# 清理旧备份 (保留30天)
find "$BACKUP_DIR" -name "*.db" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete
```

## 📞 **技术支持**

### **联系信息**
- **开发团队**: AI助手 (通过Cursor IDE)
- **技术支持**: 通过项目Issue系统
- **文档更新**: 定期更新部署指南

### **资源链接**
- **项目仓库**: [项目地址]
- **问题反馈**: [Issue页面]
- **技术文档**: [文档中心]

---

**文档版本**: 1.0
**最后更新**: 2024年8月18日
**维护人员**: AI助手

如有问题或建议，请联系开发团队。
