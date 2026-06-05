#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据库使用演示脚本
展示如何使用新创建的数据库表进行数据存储和查询
"""

import sys
import os
from pathlib import Path
import pymysql
import json
import random
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": os.environ.get("MYSQL_PASSWORD", ""),
    "database": "driving_data"
}

def connect_to_database():
    """连接到数据库"""
    try:
        connection = pymysql.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            charset='utf8mb4',
            connect_timeout=5
        )
        print("✓ 数据库连接成功")
        return connection
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return None

def insert_performance_metrics(connection, count=5):
    """插入性能指标数据"""
    try:
        with connection.cursor() as cursor:
            for i in range(count):
                # 生成模拟性能数据
                timestamp = datetime.now() - timedelta(minutes=i*5)
                sql = """
                    INSERT INTO performance_metrics 
                    (timestamp, cpu_usage, memory_usage, disk_io_read, disk_io_write,
                     network_io_upload, network_io_download, process_cpu_usage,
                     process_memory_usage, active_connections, thread_count,
                     db_connections, cache_hit_rate, response_time_avg,
                     response_time_max, error_count, warning_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                values = (
                    timestamp,
                    random.uniform(10, 90),           # cpu_usage
                    random.uniform(20, 80),           # memory_usage
                    random.randint(1000000, 5000000), # disk_io_read
                    random.randint(500000, 2000000),  # disk_io_write
                    random.randint(100000, 1000000),  # network_io_upload
                    random.randint(200000, 2000000),  # network_io_download
                    random.uniform(5, 50),            # process_cpu_usage
                    random.uniform(10, 60),           # process_memory_usage
                    random.randint(5, 50),            # active_connections
                    random.randint(10, 100),          # thread_count
                    random.randint(1, 20),            # db_connections
                    random.uniform(80, 99),           # cache_hit_rate
                    random.uniform(50, 500),          # response_time_avg
                    random.uniform(200, 2000),        # response_time_max
                    random.randint(0, 5),             # error_count
                    random.randint(0, 10)             # warning_count
                )
                cursor.execute(sql, values)
        connection.commit()
        print(f"✓ 成功插入 {count} 条性能指标数据")
        return True
    except Exception as e:
        print(f"✗ 插入性能指标数据失败: {e}")
        connection.rollback()
        return False

def insert_system_events(connection, count=5):
    """插入系统事件数据"""
    try:
        event_types = ["system_boot", "performance_warning", "security_alert", "optimization_complete", "error_occurred"]
        severities = ["info", "warning", "error", "critical"]
        source_modules = ["PerformanceMonitor", "SecurityManager", "DataOptimizer", "SystemCore", "NetworkHandler"]
        
        with connection.cursor() as cursor:
            for i in range(count):
                # 生成模拟事件数据
                event_id = f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i:03d}"
                timestamp = datetime.now() - timedelta(minutes=i*10)
                event_type = random.choice(event_types)
                severity = random.choice(severities)
                source_module = random.choice(source_modules)
                description = f"模拟系统事件: {event_type}"
                details = {
                    "event_source": source_module,
                    "additional_info": f"这是第{i+1}个模拟事件",
                    "timestamp": timestamp.isoformat()
                }
                
                sql = """
                    INSERT INTO system_events 
                    (id, timestamp, event_type, severity, source_module, description, details)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                values = (
                    event_id,
                    timestamp,
                    event_type,
                    severity,
                    source_module,
                    description,
                    json.dumps(details)
                )
                cursor.execute(sql, values)
        connection.commit()
        print(f"✓ 成功插入 {count} 条系统事件数据")
        return True
    except Exception as e:
        print(f"✗ 插入系统事件数据失败: {e}")
        connection.rollback()
        return False

def insert_optimization_logs(connection, count=5):
    """插入优化日志数据"""
    try:
        optimization_types = ["data_compression", "index_optimization", "cache_cleanup", "memory_defragmentation", "query_optimization"]
        statuses = ["success", "failed", "partial"]
        
        with connection.cursor() as cursor:
            for i in range(count):
                # 生成模拟优化日志数据
                timestamp = datetime.now() - timedelta(hours=i)
                optimization_type = random.choice(optimization_types)
                status = random.choice(statuses)
                details = f"执行了{optimization_type}优化操作"
                execution_time = random.randint(100, 5000)  # 毫秒
                space_saved = random.randint(1000000, 10000000)  # 字节
                records_processed = random.randint(100, 10000)
                
                sql = """
                    INSERT INTO optimization_logs 
                    (timestamp, optimization_type, status, details, execution_time, space_saved, records_processed)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                values = (
                    timestamp,
                    optimization_type,
                    status,
                    details,
                    execution_time,
                    space_saved,
                    records_processed
                )
                cursor.execute(sql, values)
        connection.commit()
        print(f"✓ 成功插入 {count} 条优化日志数据")
        return True
    except Exception as e:
        print(f"✗ 插入优化日志数据失败: {e}")
        connection.rollback()
        return False

def query_performance_metrics(connection, limit=10):
    """查询性能指标数据"""
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT id, timestamp, cpu_usage, memory_usage, disk_io_read, disk_io_write,
                       network_io_upload, network_io_download, process_cpu_usage,
                       process_memory_usage, active_connections, thread_count
                FROM performance_metrics
                ORDER BY timestamp DESC
                LIMIT %s
            """
            cursor.execute(sql, (limit,))
            results = cursor.fetchall()
            
            print(f"\n=== 最近 {limit} 条性能指标数据 ===")
            print(f"{'ID':<8} {'时间':<20} {'CPU%':<8} {'内存%':<8} {'磁盘读(B)':<12} {'磁盘写(B)':<12} {'网络上传(B)':<12} {'网络下载(B)':<12}")
            print("-" * 120)
            for row in results:
                print(f"{row[0]:<8} {row[1].strftime('%Y-%m-%d %H:%M:%S'):<20} {row[2]:<8.2f} {row[3]:<8.2f} {row[4]:<12} {row[5]:<12} {row[6]:<12} {row[7]:<12}")
            return True
    except Exception as e:
        print(f"✗ 查询性能指标数据失败: {e}")
        return False

def query_system_events(connection, limit=10):
    """查询系统事件数据"""
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT id, timestamp, event_type, severity, source_module, description
                FROM system_events
                ORDER BY timestamp DESC
                LIMIT %s
            """
            cursor.execute(sql, (limit,))
            results = cursor.fetchall()
            
            print(f"\n=== 最近 {limit} 条系统事件数据 ===")
            print(f"{'ID':<15} {'时间':<20} {'事件类型':<20} {'严重程度':<10} {'源模块':<20} {'描述':<30}")
            print("-" * 120)
            for row in results:
                print(f"{row[0][:14]:<15} {row[1].strftime('%Y-%m-%d %H:%M:%S'):<20} {row[2]:<20} {row[3]:<10} {row[4]:<20} {row[5][:29]:<30}")
            return True
    except Exception as e:
        print(f"✗ 查询系统事件数据失败: {e}")
        return False

def query_optimization_logs(connection, limit=10):
    """查询优化日志数据"""
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT id, timestamp, optimization_type, status, execution_time, space_saved, records_processed
                FROM optimization_logs
                ORDER BY timestamp DESC
                LIMIT %s
            """
            cursor.execute(sql, (limit,))
            results = cursor.fetchall()
            
            print(f"\n=== 最近 {limit} 条优化日志数据 ===")
            print(f"{'ID':<8} {'时间':<20} {'优化类型':<20} {'状态':<10} {'执行时间(ms)':<15} {'节省空间(B)':<15} {'处理记录数':<12}")
            print("-" * 110)
            for row in results:
                print(f"{row[0]:<8} {row[1].strftime('%Y-%m-%d %H:%M:%S'):<20} {row[2]:<20} {row[3]:<10} {row[4]:<15} {row[5]:<15} {row[6]:<12}")
            return True
    except Exception as e:
        print(f"✗ 查询优化日志数据失败: {e}")
        return False

def query_performance_trends(connection):
    """查询性能趋势数据"""
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT 
                    DATE_FORMAT(timestamp, '%Y-%m-%d %H:%i') as time_point,
                    AVG(cpu_usage) as avg_cpu,
                    AVG(memory_usage) as avg_memory,
                    AVG(response_time_avg) as avg_response_time
                FROM performance_metrics
                WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
                GROUP BY DATE_FORMAT(timestamp, '%Y-%m-%d %H:%i')
                ORDER BY time_point
            """
            cursor.execute(sql)
            results = cursor.fetchall()
            
            print("\n=== 最近1小时性能趋势 ===")
            print(f"{'时间点':<20} {'平均CPU%':<12} {'平均内存%':<12} {'平均响应时间(ms)':<18}")
            print("-" * 70)
            for row in results:
                print(f"{row[0]:<20} {row[1]:<12.2f} {row[2]:<12.2f} {row[3]:<18.2f}")
            return True
    except Exception as e:
        print(f"✗ 查询性能趋势数据失败: {e}")
        return False

def query_optimization_summary(connection):
    """查询优化摘要数据"""
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT 
                    optimization_type,
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                    AVG(execution_time) as avg_execution_time,
                    SUM(space_saved) as total_space_saved
                FROM optimization_logs
                GROUP BY optimization_type
                ORDER BY total_runs DESC
            """
            cursor.execute(sql)
            results = cursor.fetchall()
            
            print("\n=== 优化操作摘要 ===")
            print(f"{'优化类型':<25} {'总执行次数':<12} {'成功次数':<10} {'平均执行时间(ms)':<18} {'总节省空间(B)':<15}")
            print("-" * 90)
            for row in results:
                print(f"{row[0]:<25} {row[1]:<12} {row[2]:<10} {row[3]:<18.2f} {row[4]:<15}")
            return True
    except Exception as e:
        print(f"✗ 查询优化摘要数据失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 70)
    print("数据库使用演示脚本")
    print("=" * 70)
    
    # 连接数据库
    connection = connect_to_database()
    if not connection:
        print("✗ 无法连接到数据库，演示终止")
        return 1
    
    try:
        # 插入演示数据
        print("\n--- 插入演示数据 ---")
        insert_performance_metrics(connection, 10)
        insert_system_events(connection, 8)
        insert_optimization_logs(connection, 6)
        
        # 查询数据
        print("\n--- 查询数据 ---")
        query_performance_metrics(connection, 5)
        query_system_events(connection, 5)
        query_optimization_logs(connection, 5)
        
        # 高级查询
        print("\n--- 高级查询 ---")
        query_performance_trends(connection)
        query_optimization_summary(connection)
        
        print("\n" + "=" * 70)
        print("数据库使用演示完成!")
        print("=" * 70)
        print("通过本演示脚本，您可以了解如何:")
        print("  1. 连接到数据库")
        print("  2. 向新表中插入数据")
        print("  3. 查询表中的数据")
        print("  4. 执行复杂的聚合查询")
        print("  5. 获取性能趋势和优化摘要信息")
        print("\n这些操作支持以下模块:")
        print("  - 性能监控模块: performance_metrics 表")
        print("  - 系统事件管理: system_events 表")
        print("  - 优化日志记录: optimization_logs 表")
        print("=" * 70)
        
        return 0
    except Exception as e:
        print(f"✗ 演示过程中出现错误: {e}")
        return 1
    finally:
        connection.close()
        print("✓ 数据库连接已关闭")

if __name__ == "__main__":
    sys.exit(main())