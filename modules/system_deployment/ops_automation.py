import os
import logging
import subprocess
import time
import json
import schedule
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("OpsAutomation")

class SystemMonitor:
    """系统监控工具，监控应用运行状态和资源使用情况"""
    
    def __init__(self, config):
        self.config = config or {}
        self.monitoring_enabled = self.config.get("enabled", True)
        self.check_interval = self.config.get("check_interval", 60)  # 检查间隔(秒)
        self.resource_thresholds = self.config.get("resource_thresholds", {
            "cpu": 80,    # CPU使用率阈值(%)
            "memory": 80, # 内存使用率阈值(%)
            "disk": 90    # 磁盘使用率阈值(%)
        })
        self.log_file = self.config.get("log_file", "system_monitor.log")
        self.alert_recipients = self.config.get("alert_recipients", [])
        
        # 初始化监控日志
        self._init_monitor_log()
        
        # 系统状态缓存
        self.last_status = None
        self.alerts = []
    
    def _init_monitor_log(self):
        """初始化监控日志"""
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 添加文件处理器到监控日志
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
        logger.addHandler(file_handler)
    
    def get_system_status(self):
        """获取系统状态信息"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "system": self._get_system_info(),
            "resources": self._get_resource_usage(),
            "application": self._get_application_status()
        }
        
        self.last_status = status
        return status
    
    def _get_system_info(self):
        """获取系统基本信息"""
        try:
            import platform
            return {
                "os": platform.system(),
                "os_version": platform.release(),
                "hostname": platform.node(),
                "python_version": platform.python_version()
            }
        except Exception as e:
            logger.error(f"获取系统信息失败: {str(e)}")
            return {}
    
    def _get_resource_usage(self):
        """获取系统资源使用情况"""
        try:
            import psutil
            
            # CPU使用率
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # 内存使用率
            mem = psutil.virtual_memory()
            mem_usage = mem.percent
            
            # 磁盘使用率
            disk = psutil.disk_usage('/')
            disk_usage = disk.percent
            
            # 网络使用情况
            net_io = psutil.net_io_counters()
            
            return {
                "cpu": {
                    "usage_percent": cpu_usage,
                    "cores": psutil.cpu_count(logical=False),
                    "logical_cores": psutil.cpu_count(logical=True)
                },
                "memory": {
                    "usage_percent": mem_usage,
                    "total_gb": round(mem.total / (1024 **3), 2),
                    "available_gb": round(mem.available / (1024** 3), 2)
                },
                "disk": {
                    "usage_percent": disk_usage,
                    "total_gb": round(disk.total / (1024 **3), 2),
                    "free_gb": round(disk.free / (1024** 3), 2)
                },
                "network": {
                    "bytes_sent_mb": round(net_io.bytes_sent / (1024 **2), 2),
                    "bytes_recv_mb": round(net_io.bytes_recv / (1024** 2), 2)
                }
            }
        except Exception as e:
            logger.error(f"获取资源使用情况失败: {str(e)}")
            return {}
    
    def _get_application_status(self):
        """获取应用程序状态"""
        try:
            # 检查应用是否在运行
            import psutil
            
            # 查找车辆监控系统进程
            app_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status', 'cpu_percent', 'memory_percent', 'create_time']):
                try:
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if 'vehicle_monitor' in cmdline or 'main.py' in cmdline:
                        app_processes.append({
                            "pid": proc.info['pid'],
                            "name": proc.info['name'],
                            "status": proc.info['status'],
                            "cpu_usage": proc.info['cpu_percent'],
                            "memory_usage": proc.info['memory_percent'],
                            "start_time": datetime.fromtimestamp(proc.info['create_time']).isoformat() if proc.info['create_time'] else None
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            # 检查数据库连接
            db_status = self._check_database_status()
            
            return {
                "running": len(app_processes) > 0,
                "processes": app_processes,
                "database": db_status
            }
        except Exception as e:
            logger.error(f"获取应用程序状态失败: {str(e)}")
            return {"running": False, "processes": [], "database": {}}
    
    def _check_database_status(self):
        """检查数据库状态"""
        try:
            from ui.db_handler import MySQLHandler
            from config_manager import ConfigManager
            
            config_manager = ConfigManager()
            db_handler = MySQLHandler(config_manager)
            
            # 尝试连接数据库
            start_time = time.time()
            connected = db_handler.connect()
            connect_time = round(time.time() - start_time, 3)
            
            status = {
                "connected": connected,
                "response_time_sec": connect_time,
                "last_check": datetime.now().isoformat()
            }
            
            # 如果连接成功，获取一些数据库信息
            if connected:
                try:
                    with db_handler.connection.cursor() as cursor:
                        # 获取数据库版本
                        cursor.execute("SELECT VERSION()")
                        db_version = cursor.fetchone()[0]
                        
                        # 获取表信息
                        cursor.execute("SHOW TABLES")
                        tables = [t[0] for t in cursor.fetchall()]
                        
                        # 获取记录数
                        record_counts = {}
                        for table in tables:
                            cursor.execute(f"SELECT COUNT(*) FROM {table}")
                            record_counts[table] = cursor.fetchone()[0]
                        
                        status["version"] = db_version
                        status["tables"] = tables
                        status["record_counts"] = record_counts
                finally:
                    db_handler.close()
            
            return status
        except Exception as e:
            logger.error(f"检查数据库状态失败: {str(e)}")
            return {"connected": False, "error": str(e)}
    
    def check_thresholds(self):
        """检查资源使用是否超过阈值"""
        if not self.last_status:
            self.get_system_status()
            
        if not self.last_status["resources"]:
            return []
            
        alerts = []
        resources = self.last_status["resources"]
        
        # 检查CPU阈值
        if resources["cpu"]["usage_percent"] > self.resource_thresholds["cpu"]:
            alerts.append({
                "type": "cpu",
                "level": "warning",
                "message": f"CPU使用率过高: {resources['cpu']['usage_percent']}%，超过阈值 {self.resource_thresholds['cpu']}%",
                "timestamp": datetime.now().isoformat()
            })
        
        # 检查内存阈值
        if resources["memory"]["usage_percent"] > self.resource_thresholds["memory"]:
            alerts.append({
                "type": "memory",
                "level": "warning",
                "message": f"内存使用率过高: {resources['memory']['usage_percent']}%，超过阈值 {self.resource_thresholds['memory']}%",
                "timestamp": datetime.now().isoformat()
            })
        
        # 检查磁盘阈值
        if resources["disk"]["usage_percent"] > self.resource_thresholds["disk"]:
            alerts.append({
                "type": "disk",
                "level": "critical",
                "message": f"磁盘使用率过高: {resources['disk']['usage_percent']}%，超过阈值 {self.resource_thresholds['disk']}%",
                "timestamp": datetime.now().isoformat()
            })
        
        # 检查应用状态
        if not self.last_status["application"]["running"]:
            alerts.append({
                "type": "application",
                "level": "critical",
                "message": "车辆监控系统未在运行",
                "timestamp": datetime.now().isoformat()
            })
        
        # 检查数据库状态
        if not self.last_status["application"]["database"].get("connected", False):
            alerts.append({
                "type": "database",
                "level": "critical",
                "message": "数据库连接失败",
                "timestamp": datetime.now().isoformat()
            })
        
        # 保存新警报
        self.alerts.extend(alerts)
        return alerts
    
    def start_monitoring(self, background=True):
        """开始监控系统"""
        if not self.monitoring_enabled:
            logger.info("监控已禁用，不启动监控")
            return
            
        logger.info(f"开始系统监控，检查间隔: {self.check_interval}秒")
        
        if background:
            # 后台模式，使用调度器
            schedule.every(self.check_interval).seconds.do(self._run_monitoring_cycle)
            while True:
                schedule.run_pending()
                time.sleep(1)
        else:
            # 前台模式，立即执行一次
            self._run_monitoring_cycle()
    
    def _run_monitoring_cycle(self):
        """执行一次监控周期"""
        try:
            logger.info("开始监控周期")
            
            # 获取系统状态
            self.get_system_status()
            
            # 检查阈值并生成警报
            new_alerts = self.check_thresholds()
            
            # 记录系统状态
            self._log_system_status()
            
            # 如果有新警报，发送通知
            if new_alerts and self.alert_recipients:
                self._send_alert_notifications(new_alerts)
                
            logger.info("监控周期完成")
            
        except Exception as e:
            logger.error(f"监控周期执行失败: {str(e)}")
    
    def _log_system_status(self):
        """记录系统状态到日志"""
        if not self.last_status:
            return
            
        # 简化日志输出，只记录关键指标
        resources = self.last_status["resources"]
        app_status = self.last_status["application"]
        
        status_msg = (
            f"系统状态 - "
            f"CPU: {resources.get('cpu', {}).get('usage_percent', 'N/A')}%, "
            f"内存: {resources.get('memory', {}).get('usage_percent', 'N/A')}%, "
            f"磁盘: {resources.get('disk', {}).get('usage_percent', 'N/A')}%, "
            f"应用状态: {'运行中' if app_status.get('running') else '已停止'}, "
            f"数据库: {'已连接' if app_status.get('database', {}).get('connected') else '未连接'}"
        )
        
        logger.info(status_msg)
    
    def _send_alert_notifications(self, alerts):
        """发送警报通知"""
        if not self.config.get("email_settings"):
            logger.warning("未配置邮件设置，无法发送警报通知")
            return
            
        try:
            email_settings = self.config["email_settings"]
            
            # 创建邮件内容
            msg = MIMEMultipart()
            msg['From'] = email_settings["sender"]
            msg['To'] = ", ".join(self.alert_recipients)
            msg['Subject'] = f"车辆监控系统警报 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # 邮件正文
            alert_text = "<h2>车辆监控系统检测到以下问题:</h2>\n<ul>"
            for alert in alerts:
                alert_text += f"<li><strong>{alert['type'].upper()} {alert['level']}:</strong> {alert['message']}</li>"
            alert_text += "</ul>\n<p>请及时处理。</p>"
            
            msg.attach(MIMEText(alert_text, 'html'))
            
            # 发送邮件
            with smtplib.SMTP(email_settings["smtp_server"], email_settings["smtp_port"]) as server:
                if email_settings.get("use_tls", True):
                    server.starttls()
                server.login(email_settings["username"], email_settings["password"])
                server.send_message(msg)
            
            logger.info(f"已向 {', '.join(self.alert_recipients)} 发送 {len(alerts)} 条警报")
            
        except Exception as e:
            logger.error(f"发送警报邮件失败: {str(e)}")


class MaintenanceAutomator:
    """系统维护自动化工具"""
    
    def __init__(self, config):
        self.config = config or {}
        self.maintenance_schedule = self.config.get("schedule", {
            "backup": "daily",    # 每日备份
            "log_rotation": "daily",  # 每日日志轮转
            "db_cleanup": "weekly"    # 每周数据库清理
        })
        self.backup_dir = self.config.get("backup_dir", "backups")
        self.log_dir = self.config.get("log_dir", "logs")
        self.db_handler = None
        
        # 初始化维护任务
        self._init_scheduled_tasks()
    
    def _init_scheduled_tasks(self):
        """初始化定时任务"""
        # 配置备份任务
        if self.maintenance_schedule["backup"] == "daily":
            schedule.every().day.at("02:00").do(self.perform_backup)
            logger.info("已配置每日02:00执行备份任务")
        elif self.maintenance_schedule["backup"] == "weekly":
            schedule.every().monday.at("02:00").do(self.perform_backup)
            logger.info("已配置每周一02:00执行备份任务")
        
        # 配置日志轮转任务
        if self.maintenance_schedule["log_rotation"] == "daily":
            schedule.every().day.at("01:00").do(self.rotate_logs)
            logger.info("已配置每日01:00执行日志轮转任务")
        elif self.maintenance_schedule["log_rotation"] == "weekly":
            schedule.every().monday.at("01:00").do(self.rotate_logs)
            logger.info("已配置每周一01:00执行日志轮转任务")
        
        # 配置数据库清理任务
        if self.maintenance_schedule["db_cleanup"] == "daily":
            schedule.every().day.at("03:00").do(self.cleanup_database)
            logger.info("已配置每日03:00执行数据库清理任务")
        elif self.maintenance_schedule["db_cleanup"] == "weekly":
            schedule.every().monday.at("03:00").do(self.cleanup_database)
            logger.info("已配置每周一03:00执行数据库清理任务")
    
    def set_db_handler(self, db_handler):
        """设置数据库处理器"""
        self.db_handler = db_handler
    
    def start_maintenance(self):
        """开始维护任务调度"""
        logger.info("开始系统维护任务调度")
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次任务
    
    def perform_backup(self):
        """执行系统备份"""
        try:
            logger.info("开始执行系统备份...")
            
            # 创建备份目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_root = os.path.join(self.backup_dir, f"full_backup_{timestamp}")
            os.makedirs(backup_root, exist_ok=True)
            
            # 备份配置文件
            from deploy.deployment_manager import DeploymentManager
            dm = DeploymentManager()
            config_backup = dm.backup_configurations(os.path.join(backup_root, "config"))
            
            # 备份数据库
            db_backup_path = None
            if self.db_handler and self.db_handler.connection:
                db_backup_path = self._backup_database(backup_root)
            
            logger.info(f"系统备份完成，备份路径: {backup_root}")
            return {
                "success": True,
                "timestamp": timestamp,
                "path": backup_root,
                "config_backup": config_backup is not None,
                "db_backup": db_backup_path is not None
            }
            
        except Exception as e:
            logger.error(f"系统备份失败: {str(e)}")
            return {"success": False, "error": str(e), "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S")}
    
    def _backup_database(self, backup_dir):
        """备份数据库"""
        try:
            db_name = self.db_handler.config_manager.get_config("MySQLConfig").get("database", "driving_data")
            backup_file = os.path.join(backup_dir, f"db_backup_{db_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql")
            
            # 使用mysqldump命令备份数据库
            cmd = [
                "mysqldump",
                f"--host={self.db_handler.config['host']}",
                f"--port={self.db_handler.config['port']}",
                f"--user={self.db_handler.config['user']}",
                f"--password={self.db_handler.config['password']}",
                db_name,
                f"--result-file={backup_file}"
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0 and os.path.exists(backup_file) and os.path.getsize(backup_file) > 0:
                logger.info(f"数据库备份成功: {backup_file}")
                return backup_file
            else:
                logger.error(f"数据库备份失败: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"数据库备份过程中发生错误: {str(e)}")
            return None
    
    def rotate_logs(self):
        """执行日志轮转"""
        try:
            logger.info("开始执行日志轮转...")
            
            if not os.path.exists(self.log_dir):
                logger.warning(f"日志目录不存在: {self.log_dir}")
                return {"success": False, "error": "日志目录不存在"}
            
            rotated_count = 0
            
            # 遍历日志目录中的所有日志文件
            for filename in os.listdir(self.log_dir):
                if filename.endswith(".log") and not filename.endswith(".log.gz"):
                    log_path = os.path.join(self.log_dir, filename)
                    
                    # 压缩日志文件
                    try:
                        import gzip
                        with open(log_path, 'rb') as f_in:
                            with gzip.open(f"{log_path}.gz", 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        
                        # 清空原始日志文件
                        with open(log_path, 'w') as f:
                            pass  # 清空文件
                        
                        rotated_count += 1
                        logger.info(f"已轮转日志文件: {filename}")
                    except Exception as e:
                        logger.error(f"轮转日志文件 {filename} 失败: {str(e)}")
            
            # 删除过期的日志备份（保留30天）
            thirty_days_ago = datetime.now() - timedelta(days=30)
            for filename in os.listdir(self.log_dir):
                if filename.endswith(".log.gz"):
                    log_path = os.path.join(self.log_dir, filename)
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(log_path))
                    
                    if file_mtime < thirty_days_ago:
                        try:
                            os.remove(log_path)
                            logger.info(f"已删除过期日志备份: {filename}")
                        except Exception as e:
                            logger.error(f"删除过期日志备份 {filename} 失败: {str(e)}")
            
            logger.info(f"日志轮转完成，共处理 {rotated_count} 个日志文件")
            return {"success": True, "rotated_count": rotated_count}
            
        except Exception as e:
            logger.error(f"日志轮转失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def cleanup_database(self, keep_days=30):
        """清理数据库，删除旧数据"""
        try:
            if not self.db_handler or not self.db_handler.connection:
                logger.warning("数据库连接未建立，无法执行清理任务")
                return {"success": False, "error": "数据库连接未建立"}
            
            logger.info(f"开始执行数据库清理，保留最近 {keep_days} 天的数据...")
            
            deleted_counts = {}
            
            with self.db_handler.connection.cursor() as cursor:
                # 清理驾驶数据表
                cursor.execute(f"""
                    DELETE FROM driving_data 
                    WHERE timestamp < NOW() - INTERVAL {keep_days} DAY
                """)
                deleted_counts["driving_data"] = cursor.rowcount
                
                # 清理行为事件表
                cursor.execute(f"""
                    DELETE FROM behavior_events 
                    WHERE timestamp < NOW() - INTERVAL {keep_days} DAY
                """)
                deleted_counts["behavior_events"] = cursor.rowcount
                
                # 提交事务
                self.db_handler.connection.commit()
            
            logger.info(f"数据库清理完成，删除记录数: {deleted_counts}")
            return {"success": True, "deleted_counts": deleted_counts}
            
        except Exception as e:
            if self.db_handler and self.db_handler.connection:
                self.db_handler.connection.rollback()
            logger.error(f"数据库清理失败: {str(e)}")
            return {"success": False, "error": str(e)}
