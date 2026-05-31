#!/usr/bin/env python3
import os
import sys
import logging
import argparse
import json
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("deploy_script")

def main():
    """部署脚本主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="车辆监控系统部署工具")
    parser.add_argument("--action", required=True, choices=[
        "check", "install", "configure", "package", 
        "backup-config", "restore-config", "start", "stop",
        "monitor", "maintenance"
    ], help="要执行的操作")
    parser.add_argument("--upgrade", action="store_true", help="安装依赖时升级现有包")
    parser.add_argument("--overwrite", action="store_true", help="覆盖现有配置文件")
    parser.add_argument("--output", help="指定输出文件名或路径")
    parser.add_argument("--backup-dir", help="指定备份或恢复的目录")
    parser.add_argument("--config", help="指定配置文件路径")
    
    args = parser.parse_args()
    
    # 根据不同操作执行相应功能
    try:
        if args.action == "check":
            # 检查环境
            from deployment_manager import DeploymentManager
            dm = DeploymentManager()
            success, issues = dm.check_environment()
            sys.exit(0 if success else 1)
            
        elif args.action == "install":
            # 安装依赖
            from deployment_manager import DeploymentManager
            dm = DeploymentManager()
            success = dm.install_dependencies(upgrade=args.upgrade)
            sys.exit(0 if success else 1)
            
        elif args.action == "configure":
            # 配置系统
            from deployment_manager import DeploymentManager
            dm = DeploymentManager()
            created_files = dm.create_configuration(overwrite=args.overwrite)
            if created_files:
                logger.info(f"已创建/更新 {len(created_files)} 个配置文件")
                sys.exit(0)
            else:
                logger.info("未创建任何配置文件")
                sys.exit(0)
                
        elif args.action == "package":
            # 打包应用
            from deployment_manager import DeploymentManager
            dm = DeploymentManager()
            output_path = dm.package_application(output_name=args.output)
            if output_path:
                logger.info(f"应用程序已打包至: {output_path}")
                sys.exit(0)
            else:
                logger.error("应用程序打包失败")
                sys.exit(1)
                
        elif args.action == "backup-config":
            # 备份配置
            from deployment_manager import DeploymentManager
            dm = DeploymentManager()
            backup_dir = dm.backup_configurations(backup_dir=args.backup_dir)
            if backup_dir:
                logger.info(f"配置文件已备份至: {backup_dir}")
                sys.exit(0)
            else:
                logger.error("配置文件备份失败")
                sys.exit(1)
                
        elif args.action == "restore-config":
            # 恢复配置
            if not args.backup_dir:
                logger.error("请指定要恢复的备份目录")
                sys.exit(1)
                
            from deployment_manager import DeploymentManager
            dm = DeploymentManager()
            success = dm.restore_configurations(args.backup_dir)
            if success:
                logger.info(f"已从 {args.backup_dir} 恢复配置文件")
                sys.exit(0)
            else:
                logger.error("配置文件恢复失败")
                sys.exit(1)
                
        elif args.action == "start":
            # 启动应用
            logger.info("启动车辆监控系统...")
            
            # 检查是否在开发环境
            main_script = os.path.join(os.path.dirname(__file__), "..", "main.py")
            if os.path.exists(main_script):
                # 开发环境，直接运行Python脚本
                import subprocess
                process = subprocess.Popen(["python", main_script])
                logger.info(f"车辆监控系统已启动，进程ID: {process.pid}")
                
                # 写入PID文件
                with open("vehicle_monitor.pid", "w") as f:
                    f.write(str(process.pid))
                
                sys.exit(0)
            else:
                # 生产环境，运行打包后的可执行文件
                # 查找最新的打包版本
                from deployment_manager import DeploymentManager
                dm = DeploymentManager()
                dist_dir = dm.dist_dir
                
                if not os.path.exists(dist_dir):
                    logger.error("未找到打包的应用程序，请先执行package操作")
                    sys.exit(1)
                
                # 简单起见，假设只有一个打包版本
                app_dirs = [d for d in os.listdir(dist_dir) if os.path.isdir(os.path.join(dist_dir, d))]
                if not app_dirs:
                    logger.error("未找到打包的应用程序，请先执行package操作")
                    sys.exit(1)
                
                # 取最新的目录
                app_dirs.sort(reverse=True)
                app_path = os.path.join(dist_dir, app_dirs[0], "vehicle_monitor.exe" if os.name == "nt" else "vehicle_monitor")
                
                if not os.path.exists(app_path):
                    logger.error(f"未找到应用程序可执行文件: {app_path}")
                    sys.exit(1)
                
                # 启动应用
                import subprocess
                subprocess.Popen([app_path])
                logger.info(f"车辆监控系统已启动: {app_path}")
                sys.exit(0)
                
        elif args.action == "stop":
            # 停止应用
            logger.info("停止车辆监控系统...")
            
            try:
                # 读取PID文件
                if os.path.exists("vehicle_monitor.pid"):
                    with open("vehicle_monitor.pid", "r") as f:
                        pid = int(f.read().strip())
                    
                    # 终止进程
                    import os
                    import signal
                    os.kill(pid, signal.SIGTERM)
                    logger.info(f"已终止进程 {pid}")
                    
                    # 删除PID文件
                    os.remove("vehicle_monitor.pid")
                    sys.exit(0)
                else:
                    # 尝试查找并终止进程
                    import psutil
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        try:
                            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                            if 'vehicle_monitor' in cmdline or 'main.py' in cmdline:
                                proc.terminate()
                                logger.info(f"已终止进程 {proc.info['pid']}")
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    
                    logger.info("车辆监控系统已停止")
                    sys.exit(0)
                    
            except Exception as e:
                logger.error(f"停止应用程序失败: {str(e)}")
                sys.exit(1)
                
        elif args.action == "monitor":
            # 启动系统监控
            logger.info("启动系统监控...")
            
            # 加载监控配置
            monitor_config = {}
            if args.config and os.path.exists(args.config):
                with open(args.config, 'r') as f:
                    monitor_config = json.load(f)
            
            from ops_automation import SystemMonitor
            monitor = SystemMonitor(monitor_config)
            monitor.start_monitoring()
            
        elif args.action == "maintenance":
            # 启动维护任务
            logger.info("启动系统维护任务...")
            
            # 加载维护配置
            maintenance_config = {}
            if args.config and os.path.exists(args.config):
                with open(args.config, 'r') as f:
                    maintenance_config = json.load(f)
            
            from ops_automation import MaintenanceAutomator
            from ui.db_handler import MySQLHandler
            from ui.config.config_manager import ConfigManager

            from config_manager import ConfigManager

            # 初始化数据库连接
            config_manager = ConfigManager()
            db_handler = MySQLHandler(config_manager)
            db_handler.connect()
            
            # 启动维护任务
            automator = MaintenanceAutomator(maintenance_config)
            automator.set_db_handler(db_handler)
            automator.start_maintenance()
            
    except Exception as e:
        logger.error(f"执行操作失败: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
