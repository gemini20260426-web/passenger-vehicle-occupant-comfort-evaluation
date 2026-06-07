#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MySQL数据库处理器
处理MySQL数据库连接和操作
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from PySide6.QtCore import QObject, Signal
import time

# 初始化日志记录器
logger = logging.getLogger(__name__)

# 强制使用pymysql作为MySQL连接器
try:
    import pymysql
    logger.info("强制使用pymysql作为MySQL连接器")
    USE_PYMYSQL = True
except ImportError:
    logger.warning("未找到pymysql，MySQL功能将不可用")
    USE_PYMYSQL = False
    pymysql = None


def _safe_log_params(params: dict) -> dict:
    """脱敏日志 — 隐藏密码/密钥等敏感字段 (E6 修复)"""
    safe = dict(params)
    for key in ('password', 'passwd', 'pwd', 'secret', 'token'):
        if key in safe:
            safe[key] = '******'
    return safe


# 为pymysql添加Error定义，保持代码兼容性
if pymysql is not None:
    class Error(Exception):
        pass
    pymysql.Error = Error

class MySQLHandler(QObject):
    # 数据库连接状态信号
    mysql_connected = Signal()
    mysql_disconnected = Signal(str)
    mysql_error = Signal(str)
    """MySQL数据库处理器"""
    
    def __init__(self, config_manager=None):
        """
        初始化MySQL处理器
        
        Args:
            config_manager: 配置管理器实例
        """
        super().__init__()  # 调用父类QObject的初始化方法
        self.logger = logging.getLogger("MySQLHandler")
        self.connection = None
        self.config_manager = config_manager
        
        # 从配置管理器获取MySQL配置
        if self.config_manager:
            try:
                mysql_config = self.config_manager.get_section("MySQLConfig") or {}
                self.logger.info(f"从配置管理器获取MySQL配置成功: {mysql_config.get('host')}:{mysql_config.get('port')}")
            except Exception as e:
                self.logger.warning(f"从配置管理器获取MySQL配置失败: {e}，使用默认配置")
                mysql_config = {}
        else:
            # 默认配置
            mysql_config = {
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "",
                "database": "driving_data"
            }
        
        self.host = mysql_config.get("host", "localhost")
        self.port = int(mysql_config.get("port", 3306))  # 确保端口号为整数类型
        self.user = mysql_config.get("user", "root")
        # 获取密码
        self.password = mysql_config.get("password", "")
        self.database = mysql_config.get("database", "driving_data")
        
        # 其他连接参数
        self.connect_timeout = int(mysql_config.get("connect_timeout", 10))  # 增加默认超时到10秒
        self.charset = mysql_config.get("charset", "utf8mb4")
        
        # SSL配置
        self.ssl_enabled = mysql_config.get("ssl_enabled", False)
        self.ssl_ca = mysql_config.get("ssl_ca", None)
        self.ssl_cert = mysql_config.get("ssl_cert", None)
        self.ssl_key = mysql_config.get("ssl_key", None)
        
        # 记录配置信息（不记录密码）
        self.logger.info(f"MySQL处理器初始化完成: host={self.host}, port={self.port}, "
                        f"user={self.user}, database={self.database}, timeout={self.connect_timeout}")

    def connect(self):
        """连接到MySQL数据库"""
        if not USE_PYMYSQL:
            self.logger.warning("pymysql不可用，无法连接MySQL")
            return False
        try:
            self.logger.info("开始连接MySQL数据库")
            # 检查连接是否存在且有效
            if self.connection:
                if USE_PYMYSQL:
                    try:
                        self.connection.ping()
                        self.logger.info("数据库连接已存在且有效")
                        self.mysql_connected.emit()
                        return True
                    except:
                        self.logger.info("数据库连接已存在但无效，重新连接...")
                else:
                    if self.connection.is_connected():
                        self.logger.info("数据库连接已存在")
                        self.mysql_connected.emit()
                        return True

            self.logger.info(f"正在建立数据库连接: host={self.host}, port={self.port}, user={self.user}, database={self.database}")
            
            # 构建连接参数
            connection_params = {
                'host': str(self.host),
                'port': int(self.port),
                'user': str(self.user),
                'password': str(self.password),
                'database': str(self.database),
                'charset': str(self.charset),
                'autocommit': True
            }
            
            # 根据不同的连接器设置超时参数
            if USE_PYMYSQL:
                connection_params['connect_timeout'] = int(self.connect_timeout)
            else:
                connection_params['connection_timeout'] = int(self.connect_timeout)
            
            # SSL配置
            if self.ssl_enabled:
                self.logger.info("SSL已启用")
                ssl_options = {}
                if self.ssl_ca:
                    ssl_options['ca'] = self.ssl_ca
                if self.ssl_cert:
                    ssl_options['cert'] = self.ssl_cert
                if self.ssl_key:
                    ssl_options['key'] = self.ssl_key
                if ssl_options:
                    connection_params['ssl_disabled'] = False
                    connection_params['ssl_verify_cert'] = True
                    connection_params['ssl_verify_identity'] = True
                    connection_params.update(ssl_options)
                else:
                    connection_params['ssl_disabled'] = True
            else:
                self.logger.info("SSL未启用")
                connection_params['ssl_disabled'] = True
            
            self.logger.info(f"连接参数: {_safe_log_params(connection_params)}")
            
            # 记录开始连接时间
            start_time = time.time()
            self.logger.info("开始建立数据库连接...")
            
            # 添加try-except块捕获连接过程中的异常
            try:
                if USE_PYMYSQL:
                    self.connection = pymysql.connect(**connection_params)
                else:
                    self.connection = mysql.connector.connect(**connection_params)
            except Exception as conn_e:
                self.logger.error(f"连接过程中发生异常: {conn_e}")
                self.logger.exception("连接异常详情:")
                self.mysql_error.emit(f"连接过程中发生异常: {conn_e}")
                return False
            
            # 记录连接耗时
            end_time = time.time()
            connect_duration = end_time - start_time
            self.logger.info(f"数据库连接建立耗时: {connect_duration:.2f}秒")

            try:
                # 对于pymysql，使用ping()检查连接并获取服务器信息
                if USE_PYMYSQL:
                    self.connection.ping()
                    # pymysql通过get_server_info()获取服务器版本
                    db_info = self.connection.get_server_info()
                else:
                    if self.connection.is_connected():
                        db_info = self.connection.get_server_info()
                self.logger.info(f"成功连接到MySQL数据库 {self.host}:{self.port}，服务器版本: {db_info}")
                self.mysql_connected.emit()
                return True
            except Exception as info_e:
                self.logger.error(f"获取服务器信息失败: {info_e}")
                self.logger.error(f"无法连接到MySQL数据库: {info_e}")
                self.mysql_error.emit(f"无法连接到MySQL数据库: {info_e}")
                return False

        except Error as e:
            error_msg = f"MySQL连接失败: {e}"
            self.logger.error(error_msg)
            self.logger.error(f"连接参数: host={self.host}, port={self.port}, user={self.user}, database={self.database}")
            self.mysql_error.emit(error_msg)
            return False
        except Exception as e:
            error_msg = f"MySQL连接异常: {e}"
            self.logger.error(error_msg)
            self.logger.exception("MySQL连接异常详情:")
            self.mysql_error.emit(error_msg)
            return False

    def disconnect(self):
        """断开数据库连接"""
        try:
            if self.connection:
                if USE_PYMYSQL:
                    # 对于pymysql，直接关闭连接
                    self.connection.close()
                    self.logger.info("MySQL连接已关闭")
                else:
                    if self.connection.is_connected():
                        self.connection.close()
                        self.logger.info("MySQL连接已关闭")
            self.connection = None
        except Exception as e:
            self.logger.error(f"关闭MySQL连接时发生错误: {e}")
            self.logger.exception("关闭连接异常详情:")
            self.logger.info("MySQL数据库连接已断开")
            self.mysql_disconnected.emit("正常断开连接")

    def is_connected(self):
        """检查数据库连接状态"""
        try:
            return self.connection and self.connection.is_connected()
        except:
            return False

    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[Dict]:
        """
        执行查询语句

        Args:
            query: SQL查询语句
            params: 查询参数

        Returns:
            查询结果列表
        """
        if not self.is_connected() and not self.connect():
            return []

        try:
            # 使用pymysql兼容的方式创建cursor
            if USE_PYMYSQL:
                cursor = self.connection.cursor()
            else:
                cursor = self.connection.cursor(dictionary=True)
            
            cursor.execute(query, params or ())
            result = cursor.fetchall()
            
            # 如果使用pymysql，需要手动将结果转换为字典列表
            if USE_PYMYSQL:
                if cursor.description:
                    column_names = [desc[0] for desc in cursor.description]
                    result = [dict(zip(column_names, row)) for row in result]
            
            cursor.close()
            return result
        except Error as e:
            self.logger.error(f"执行查询失败: {e}")
            self.logger.error(f"查询语句: {query}")
            return []
        except Exception as e:
            self.logger.error(f"执行查询异常: {e}")
            return []

    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """
        执行更新语句

        Args:
            query: SQL更新语句
            params: 更新参数

        Returns:
            受影响的行数
        """
        if not self.is_connected() and not self.connect():
            return 0

        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params or ())
            self.connection.commit()
            rowcount = cursor.rowcount
            cursor.close()
            return rowcount
        except Error as e:
            self.logger.error(f"执行更新失败: {e}")
            self.logger.error(f"更新语句: {query}")
            self.connection.rollback()
            return 0
        except Exception as e:
            self.logger.error(f"执行更新异常: {e}")
            self.connection.rollback()
            return 0

    def test_connection(self) -> bool:
        """
        测试数据库连接

        Returns:
            bool: 连接是否成功
        """
        try:
            # 尝试连接
            success = self.connect()
            if success:
                # 执行简单查询测试
                result = self.execute_query("SELECT 1 as test")
                self.disconnect()
                return len(result) > 0
            return False
        except Exception as e:
            self.logger.error(f"测试数据库连接失败: {e}")
            return False
            
    def close(self):
        """
        关闭数据库连接
        这个方法是为了与主控制器中的关闭逻辑兼容
        """
        self.disconnect()