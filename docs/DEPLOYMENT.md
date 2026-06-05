# 部署指南 — 乘用车座椅综合性能评测系统 v3.5

## 环境要求

| 组件 | 版本要求 |
|------|----------|
| Python | 3.9+ |
| PySide6 | 6.5+ |
| NumPy | 1.24+ |
| SciPy | 1.10+ |
| Pandas | 1.5+ |
| InfluxDB | 2.7+ (可选，用于时序数据存储) |
| SQLite | 3.35+ (内置) |

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动应用
python main/main.py
```

## 配置文件

主配置文件位于 `config/config.ini`：

```ini
[paths]
data_dir = data
output_dir = data_output

[influxdb]
url = http://localhost:8086
token = <your-token>
org = <your-org>
bucket = <your-bucket>

[imu]
default_sample_rate = 100.0
```

## 目录结构

```
project_root/
├── main/                  # 应用入口
├── config/               # 配置文件
├── core/                 # 核心模块
│   └── core/
│       ├── seat_evaluation/  # 评测引擎
│       ├── analysis/         # 分析模块
│       └── data_processing/  # 数据处理
├── modules/              # 功能模块
│   └── ui/               # 用户界面
├── data/                 # 数据存储
├── data_output/          # 输出数据
├── docs/                 # 文档
├── test/                 # 测试
└── logs/                 # 日志
```

## 常见问题

### Q: 启动报错 "No module named 'PySide6'"
```bash
pip install PySide6
```

### Q: InfluxDB 连接失败
检查 `config/config.ini` 中的 InfluxDB 配置，确保服务已启动：
```bash
influxd
```

### Q: 回放控制器显示"未知 0条"
缓存注册表为空，系统会自动扫描 `data_output/` 目录重新注册缓存文件。

### Q: IMU 可视化卡顿
已优化：瓦片 UI 更新频率从每帧 1600 次降至 8 次。若仍卡顿，可降低采样率或增大时间窗口。

## 日志

日志文件位于 `logs/` 目录：
- `app.log` — 应用日志
- `error.log` — 错误日志
- `debug.log` — 调试日志