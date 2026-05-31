# 文件数据源使用指南

## 概述

文件数据源接口允许系统从离线文件读取数据，支持多种文件格式，适用于开发和测试环境。

## 支持的文件格式

### 1. CSV格式
- 自动检测分隔符（逗号、制表符、分号、竖线）
- 支持标题行
- 自动类型转换（数值/字符串）

### 2. JSON格式
- 支持数组和对象格式
- 自动解析嵌套结构
- 类型保持

### 3. TXT格式
- 支持多种分隔符
- 自动格式检测
- 灵活的数据解析

## 配置示例

### 基本配置
```json
{
    "type": "file",
    "file_path": "test/cnapdata/1.txt",
    "data_format": "txt",
    "sampling_rate": 10
}
```

### 高级配置
```json
{
    "type": "file",
    "file_path": "data/sensors.csv",
    "data_format": "csv",
    "sampling_rate": 15,
    "encoding": "utf-8",
    "cache_data": true
}
```

## 使用方法

### 1. 创建文件数据源
```python
from core.core.multi_source_sync.data_source_interfaces import DataSourceFactory

# 创建文件数据源
config = {
    "file_path": "test/cnapdata/1.txt",
    "data_format": "txt",
    "sampling_rate": 10
}

file_source = DataSourceFactory.create_data_source("file", config)
```

### 2. 连接和获取数据
```python
# 连接数据源
if file_source.connect():
    # 获取数据
    data = file_source.get_data()
    if data:
        print(f"获取到 {len(data)} 条数据")
        for sample in data:
            print(f"数据: {sample.data}")
```

### 3. 监控状态
```python
# 获取数据源状态
status = file_source.get_status()
print(f"文件路径: {status['file_path']}")
print(f"数据格式: {status['data_format']}")
print(f"总记录数: {status['total_records']}")
print(f"当前进度: {status['progress']}")
```

## 文件格式要求

### CSV文件
```csv
timestamp,value1,value2,value3
2024-01-01 12:00:00,120.5,80.2,75
2024-01-01 12:00:01,121.1,79.8,76
```

### JSON文件
```json
[
    {
        "timestamp": "2024-01-01 12:00:00",
        "value1": 120.5,
        "value2": 80.2,
        "value3": 75
    },
    {
        "timestamp": "2024-01-01 12:00:01",
        "value1": 121.1,
        "value2": 79.8,
        "value3": 76
    }
]
```

### TXT文件
```
2024-01-01 12:00:00,120.5,80.2,75
2024-01-01 12:00:01,121.1,79.8,76
2024-01-01 12:00:02,119.8,81.0,74
```

## 性能优化

### 1. 采样率设置
- 根据文件大小和系统性能调整采样率
- 建议范围：1-50 Hz

### 2. 缓存策略
- 启用数据缓存以提高性能
- 大文件建议使用流式处理

### 3. 内存管理
- 自动限制缓冲区大小
- 支持数据分块处理

## 错误处理

### 1. 文件不存在
```
❌ 文件不存在: test/cnapdata/1.txt
```

### 2. 格式错误
```
⚠️ 不支持的文件格式: xml
```

### 3. 解析失败
```
⚠️ CSV文件解析失败: [Errno 2] No such file or directory
```

## 故障排除

### 1. 检查文件路径
```bash
# 确认文件存在
ls -la test/cnapdata/1.txt

# 检查文件权限
chmod 644 test/cnapdata/1.txt
```

### 2. 验证文件格式
```python
# 测试文件读取
with open("test/cnapdata/1.txt", "r") as f:
    first_line = f.readline()
    print(f"第一行: {first_line}")
```

### 3. 检查编码
```python
# 尝试不同编码
encodings = ['utf-8', 'gbk', 'latin-1']
for encoding in encodings:
    try:
        with open("test/cnapdata/1.txt", "r", encoding=encoding) as f:
            content = f.read()
            print(f"编码 {encoding} 成功")
            break
    except UnicodeDecodeError:
        print(f"编码 {encoding} 失败")
```

## 最佳实践

### 1. 文件组织
- 使用清晰的目录结构
- 统一命名规范
- 定期清理临时文件

### 2. 数据质量
- 验证数据完整性
- 检查数据范围
- 处理异常值

### 3. 性能监控
- 监控文件读取速度
- 跟踪内存使用
- 优化采样率

## 总结

文件数据源接口提供了灵活、高效的离线数据处理能力，支持多种文件格式，适用于各种开发和测试场景。通过合理配置和优化，可以实现稳定的数据流模拟。
