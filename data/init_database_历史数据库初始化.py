#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据库初始化脚本
用于创建车辆监控系统所需的所有数据表
"""

import pymysql
import logging
import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DatabaseInit")

def get_db_config():
    """获取数据库配置"""
    # 首先尝试从config.ini读取配置
    try:
        from config_manager import ConfigManager
        config_manager = ConfigManager()
        mysql_config = config_manager.get_config("MySQLConfig") or {}
        
        if mysql_config:
            config = {
                "host": mysql_config.get("host", "localhost"),
                "port": int(mysql_config.get("port", 3306)),
                "user": mysql_config.get("username", mysql_config.get("user", "root")),
                "password": mysql_config.get("password", ""),
                "db": mysql_config.get("database", mysql_config.get("db", "vehicle_monitor"))
            }
            logger.info("✓ 成功从config.ini读取数据库配置")
            return config
    except Exception as e:
        logger.warning(f"无法从ConfigManager读取数据库配置: {e}")
    
    # 尝试直接读取config.ini
    try:
        import configparser
        config_parser = configparser.ConfigParser()
        config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.ini')
        
        if os.path.exists(config_file):
            config_parser.read(config_file, encoding='utf-8')
            if 'MySQLConfig' in config_parser:
                mysql_config = config_parser['MySQLConfig']
                config = {
                    "host": mysql_config.get("host", "localhost"),
                    "port": int(mysql_config.get("port", 3306)),
                    "user": mysql_config.get("username", mysql_config.get("user", "root")),
                    "password": mysql_config.get("password", ""),
                    "db": mysql_config.get("database", mysql_config.get("db", "vehicle_monitor"))
                }
                logger.info("✓ 成功从config.ini直接读取数据库配置")
                return config
    except Exception as e:
        logger.warning(f"无法直接从config.ini读取数据库配置: {e}")
    
    # 默认配置
    config = {
        "host": os.environ.get("MYSQL_HOST", "localhost"),
        "port": int(os.environ.get("MYSQL_PORT", 3306)),
        "user": os.environ.get("MYSQL_USER", "root"),
        "password": os.environ.get("MYSQL_PASSWORD", ""),
        "db": os.environ.get("MYSQL_DATABASE", "vehicle_monitor")
    }
    
    logger.info("使用默认配置或环境变量配置")
    return config

def create_database_if_not_exists(config):
    """创建数据库（如果不存在）"""
    try:
        # 先连接到默认数据库
        temp_conn = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database="mysql",
            charset='utf8mb4'
        )
        
        with temp_conn.cursor() as cursor:
            # 创建数据库
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{config['db']}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            logger.info(f"数据库 {config['db']} 创建成功或已存在")
        
        temp_conn.close()
        return True
    except Exception as e:
        logger.error(f"创建数据库失败: {e}")
        return False

def init_tables(config):
    """初始化所有数据表"""
    try:
        # 连接到目标数据库
        connection = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["db"],
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            # 1. 驾驶数据表（原始传感器数据）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS driving_data (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    timestamp DATETIME NOT NULL,
                    speed FLOAT DEFAULT 0,
                    acceleration_x FLOAT DEFAULT 0,
                    acceleration_y FLOAT DEFAULT 0,
                    acceleration_z FLOAT DEFAULT 0,
                    gyro_x FLOAT DEFAULT 0,
                    gyro_y FLOAT DEFAULT 0,
                    gyro_z FLOAT DEFAULT 0,
                    wheel_angle FLOAT DEFAULT 0,
                    latitude FLOAT DEFAULT 0,
                    longitude FLOAT DEFAULT 0,
                    behaviors JSON,
                    INDEX idx_timestamp (timestamp)
                ) ENGINE=InnoDB
            """)
            logger.info("数据表 driving_data 创建成功或已存在")
            
            # 2. 行为事件表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS behavior_events (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    timestamp DATETIME NOT NULL,
                    speed FLOAT DEFAULT 0,
                    behaviors JSON,
                    INDEX idx_timestamp (timestamp)
                ) ENGINE=InnoDB
            """)
            logger.info("数据表 behavior_events 创建成功或已存在")
            
            # 3. 用户表（安全管理模块）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(50) PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    name VARCHAR(100),
                    email VARCHAR(100),
                    phone VARCHAR(20),
                    status ENUM('active', 'inactive') DEFAULT 'active',
                    last_login DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_username (username),
                    INDEX idx_role (role)
                ) ENGINE=InnoDB
            """)
            logger.info("数据表 users 创建成功或已存在")
            
            # 4. 操作日志表（日志管理模块）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    timestamp DATETIME NOT NULL,
                    user_id VARCHAR(50),
                    operation VARCHAR(100) NOT NULL,
                    details TEXT,
                    ip_address VARCHAR(45),
                    INDEX idx_timestamp (timestamp),
                    INDEX idx_user_id (user_id),
                    INDEX idx_operation (operation)
                ) ENGINE=InnoDB
            """)
            logger.info("数据表 operation_logs 创建成功或已存在")
            
            # 5. 车辆信息表（车辆管理模块）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vehicles (
                    id VARCHAR(50) PRIMARY KEY,
                    license_plate VARCHAR(20) NOT NULL UNIQUE,
                    brand VARCHAR(50),
                    model VARCHAR(50),
                    year INT,
                    vin VARCHAR(50),
                    status ENUM('active', 'maintenance', 'inactive') DEFAULT 'inactive',
                    driver_id VARCHAR(50),
                    mileage FLOAT DEFAULT 0,
                    fuel_level FLOAT DEFAULT 100,
                    last_maintenance DATE,
                    next_maintenance DATE,
                    notes TEXT,
                    config_params JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_license_plate (license_plate),
                    INDEX idx_status (status),
                    INDEX idx_driver_id (driver_id)
                ) ENGINE=InnoDB
            """)
            logger.info("数据表 vehicles 创建成功或已存在")
            
            # 6. 驾驶员信息表（驾驶员管理模块）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS drivers (
                    id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    license_number VARCHAR(50) NOT NULL UNIQUE,
                    license_type VARCHAR(20),
                    hire_date DATE NOT NULL,
                    birth_date DATE,
                    gender ENUM('male', 'female', ''),
                    phone VARCHAR(20),
                    email VARCHAR(100),
                    address TEXT,
                    status ENUM('active', 'suspended', 'inactive') DEFAULT 'active',
                    behavior_score FLOAT DEFAULT 100.0,
                    alarm_count INT DEFAULT 0,
                    last_evaluation DATE,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_license_number (license_number),
                    INDEX idx_status (status),
                    INDEX idx_behavior_score (behavior_score)
                ) ENGINE=InnoDB
            """)
            logger.info("数据表 drivers 创建成功或已存在")
            
            # 7. 车队信息表（车队管理模块）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fleets (
                    id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    manager VARCHAR(100),
                    contact VARCHAR(50),
                    vehicle_ids JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_name (name)
                ) ENGINE=InnoDB
            """)
            logger.info("数据表 fleets 创建成功或已存在")
            
            # 8. 告警历史表（告警管理模块）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alarm_history (
                    id VARCHAR(50) PRIMARY KEY,
                    timestamp DATETIME NOT NULL,
                    level ENUM('normal', 'serious', 'emergency') NOT NULL,
                    behavior VARCHAR(100) NOT NULL,
                    confidence FLOAT NOT NULL,
                    details TEXT,
                    handled BOOLEAN DEFAULT FALSE,
                    handler VARCHAR(50),
                    handled_time DATETIME,
                    INDEX idx_timestamp (timestamp),
                    INDEX idx_level (level),
                    INDEX idx_behavior (behavior),
                    INDEX idx_handled (handled)
                ) ENGINE=InnoDB
            """)
            logger.info("数据表 alarm_history 创建成功或已存在")
            
            # 9. 行程信息表（行程管理模块）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trips (
                    id VARCHAR(50) PRIMARY KEY,
                    vehicle_id VARCHAR(50) NOT NULL,
                    driver_id VARCHAR(50) NOT NULL,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    start_location JSON,
                    end_location JSON,
                    distance FLOAT DEFAULT 0.0,
                    duration INT DEFAULT 0,
                    max_speed FLOAT DEFAULT 0.0,
                    avg_speed FLOAT DEFAULT 0.0,
                    fuel_consumption FLOAT DEFAULT 0.0,
                    behavior_evaluation JSON,
                    status ENUM('in_progress', 'completed', 'cancelled') DEFAULT 'in_progress',
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_vehicle_id (vehicle_id),
                    INDEX idx_driver_id (driver_id),
                    INDEX idx_status (status),
                    INDEX idx_start_time (start_time)
                ) ENGINE=InnoDB
            """)
            logger.info("数据表 trips 创建成功或已存在")
            
        connection.commit()
        connection.close()
        logger.info("所有数据表初始化完成")
        return True
        
    except Exception as e:
        logger.error(f"初始化数据表失败: {e}")
        return False

def insert_default_data(config):
    """插入默认数据"""
    try:
        connection = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["db"],
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            # 检查是否已存在默认用户
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
            result = cursor.fetchone()
            
            if result[0] == 0:
                # 插入默认管理员用户 (密码: admin123)
                import bcrypt
                hashed_password = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                
                cursor.execute("""
                    INSERT INTO users 
                    (id, username, password, role, name, email, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    'user_1',
                    'admin',
                    hashed_password,
                    'admin',
                    '系统管理员',
                    'admin@example.com',
                    'active',
                    datetime.now()
                ))
                logger.info("默认管理员用户已创建")
            else:
                logger.info("默认管理员用户已存在")
        
        connection.commit()
        connection.close()
        return True
        
    except Exception as e:
        logger.error(f"插入默认数据失败: {e}")
        return False

def main():
    """主函数"""
    logger.info("开始初始化数据库...")
    
    # 获取数据库配置
    config = get_db_config()
    logger.info(f"使用配置: host={config['host']}, port={config['port']}, user={config['user']}, db={config['db']}")
    
    # 创建数据库
    if not create_database_if_not_exists(config):
        logger.error("创建数据库失败")
        return False
    
    # 初始化数据表
    if not init_tables(config):
        logger.error("初始化数据表失败")
        return False
    
    # 插入默认数据
    if not insert_default_data(config):
        logger.error("插入默认数据失败")
        return False
    
    logger.info("数据库初始化完成!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)