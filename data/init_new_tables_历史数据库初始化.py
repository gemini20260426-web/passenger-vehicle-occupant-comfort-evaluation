#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
独立的数据库表初始化脚本
为新集成模块创建对应的数据库表
"""

import pymysql
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DatabaseInit")

# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "62215587",
    "database": "driving_data"
}

# 新表结构定义
NEW_TABLE_STRUCTS = {
    "performance_metrics": """
        CREATE TABLE IF NOT EXISTS performance_metrics (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            timestamp DATETIME NOT NULL,
            cpu_usage FLOAT DEFAULT 0,
            memory_usage FLOAT DEFAULT 0,
            disk_io_read BIGINT DEFAULT 0,
            disk_io_write BIGINT DEFAULT 0,
            network_io_upload BIGINT DEFAULT 0,
            network_io_download BIGINT DEFAULT 0,
            process_cpu_usage FLOAT DEFAULT 0,
            process_memory_usage FLOAT DEFAULT 0,
            active_connections INT DEFAULT 0,
            thread_count INT DEFAULT 0,
            db_connections INT DEFAULT 0,
            cache_hit_rate FLOAT DEFAULT 0,
            response_time_avg FLOAT DEFAULT 0,
            response_time_max FLOAT DEFAULT 0,
            error_count INT DEFAULT 0,
            warning_count INT DEFAULT 0,
            INDEX idx_timestamp (timestamp)
        ) ENGINE=InnoDB
    """,
    "system_events": """
        CREATE TABLE IF NOT EXISTS system_events (
            id VARCHAR(50) PRIMARY KEY,
            timestamp DATETIME NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            severity ENUM('info', 'warning', 'error', 'critical') DEFAULT 'info',
            source_module VARCHAR(100),
            description TEXT,
            details JSON,
            handled BOOLEAN DEFAULT FALSE,
            handler VARCHAR(50),
            handled_time DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_timestamp (timestamp),
            INDEX idx_event_type (event_type),
            INDEX idx_severity (severity),
            INDEX idx_source_module (source_module),
            INDEX idx_handled (handled)
        ) ENGINE=InnoDB
    """,
    "optimization_logs": """
        CREATE TABLE IF NOT EXISTS optimization_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            timestamp DATETIME NOT NULL,
            optimization_type VARCHAR(50) NOT NULL,
            status ENUM('success', 'failed', 'partial') DEFAULT 'success',
            details TEXT,
            execution_time INT DEFAULT 0,
            space_saved BIGINT DEFAULT 0,
            records_processed INT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_timestamp (timestamp),
            INDEX idx_optimization_type (optimization_type),
            INDEX idx_status (status)
        ) ENGINE=InnoDB
    """
}

def create_database_if_not_exists():
    """创建数据库（如果不存在）"""
    try:
        # 连接到MySQL服务器（不指定数据库）
        connection = pymysql.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            # 创建数据库
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            logger.info(f"数据库 {DB_CONFIG['database']} 创建成功或已存在")
            
        connection.close()
        return True
    except Exception as e:
        logger.error(f"创建数据库失败: {e}")
        return False

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
        logger.info("数据库连接成功")
        return connection
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None

def create_new_tables(connection):
    """创建新表"""
    try:
        with connection.cursor() as cursor:
            for table_name, table_struct in NEW_TABLE_STRUCTS.items():
                cursor.execute(table_struct)
                logger.info(f"数据表 {table_name} 创建成功或已存在")
        connection.commit()
        return True
    except Exception as e:
        logger.error(f"创建数据表失败: {e}")
        connection.rollback()
        return False

def verify_tables(connection):
    """验证表是否创建成功"""
    try:
        with connection.cursor() as cursor:
            for table_name in NEW_TABLE_STRUCTS.keys():
                cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
                result = cursor.fetchone()
                if result:
                    logger.info(f"✓ 表 {table_name} 存在")
                else:
                    logger.error(f"✗ 表 {table_name} 不存在")
                    return False
        return True
    except Exception as e:
        logger.error(f"验证表失败: {e}")
        return False

def main():
    """主函数"""
    logger.info("开始初始化新数据库表...")
    
    # 创建数据库（如果不存在）
    if not create_database_if_not_exists():
        logger.error("无法创建数据库")
        return 1
    
    # 连接数据库
    connection = connect_to_database()
    if not connection:
        logger.error("无法连接到数据库")
        return 1
    
    try:
        # 创建新表
        if not create_new_tables(connection):
            logger.error("创建新表失败")
            return 1
        
        # 验证表
        if not verify_tables(connection):
            logger.error("表验证失败")
            return 1
            
        logger.info("所有新数据库表初始化成功!")
        return 0
    finally:
        connection.close()

if __name__ == "__main__":
    sys.exit(main())