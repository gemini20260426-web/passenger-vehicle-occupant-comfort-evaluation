#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统程序全量备份脚本
支持全量备份、压缩、加密等功能
"""

import os
import sys
import shutil
import zipfile
import hashlib
import json
import logging
import time
import datetime
from pathlib import Path

class SystemBackup:
    """系统备份管理器"""
    
    def __init__(self, project_root=None):
        # 修复项目根目录计算逻辑
        if project_root:
            self.project_root = project_root
        else:
            # 从当前脚本位置计算项目根目录
            # 脚本位置: tools/backup_tools/system_backup.py
            # 需要向上2级: backup_tools -> tools -> UI重构
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.project_root = os.path.dirname(os.path.dirname(script_dir))
        
        self.backup_root = os.path.join(self.project_root, "backups")
        self.config_file = os.path.join(self.project_root, "backup_config.json")
        
        # 创建备份目录
        os.makedirs(self.backup_root, exist_ok=True)
        
        # 设置日志
        self._setup_logging()
        
        # 加载配置
        self.config = self._load_config()
        
        self.logger.info(f"系统备份管理器初始化完成，项目根目录: {self.project_root}")
    
    def _setup_logging(self):
        """设置日志系统"""
        log_dir = os.path.join(self.project_root, "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"backup_{datetime.datetime.now().strftime('%Y%m%d')}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def _load_config(self):
        """加载备份配置"""
        default_config = {
            "exclude_patterns": [
                "*.pyc", "__pycache__", "*.log", "*.tmp", "*.cache",
                ".git", ".vscode", "node_modules", "venv", "env",
                ".env", "*.bak", "backups/*", "temp/*", "logs/*"
            ],
            "include_patterns": [
                "*.py", "*.md", "*.txt", "*.json", "*.xml", "*.yaml",
                "*.yml", "*.ini", "*.cfg", "*.conf", "*.html", "*.css",
                "*.js", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg"
            ],
            "compression": True,
            "encryption": False,
            "retention_days": 30
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
                    self.logger.info("已加载用户备份配置")
            except Exception as e:
                self.logger.warning(f"加载用户配置失败，使用默认配置: {e}")
        else:
            self._save_config(default_config)
            self.logger.info("已创建默认备份配置文件")
        
        return default_config
    
    def _save_config(self, config):
        """保存备份配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            self.logger.info("备份配置已保存")
        except Exception as e:
            self.logger.error(f"保存备份配置失败: {e}")
    
    def _should_backup_file(self, file_path):
        """判断文件是否应该备份"""
        file_path = file_path.lower()
        
        # 检查排除模式
        for pattern in self.config["exclude_patterns"]:
            if "*" in pattern:
                import fnmatch
                if fnmatch.fnmatch(file_path, pattern):
                    return False
            else:
                if pattern in file_path:
                    return False
        
        # 检查包含模式
        for pattern in self.config["include_patterns"]:
            if "*" in pattern:
                import fnmatch
                if fnmatch.fnmatch(file_path, pattern):
                    return True
            else:
                if pattern in file_path:
                    return True
        
        return False
    
    def _get_backup_files(self):
        """获取需要备份的文件列表"""
        backup_files = []
        total_size = 0
        
        self.logger.info("开始扫描需要备份的文件...")
        
        for root, dirs, files in os.walk(self.project_root):
            if root.startswith(self.backup_root):
                continue
            
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.project_root)
                
                if self._should_backup_file(rel_path):
                    try:
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        backup_files.append((rel_path, file_path, file_size))
                    except Exception as e:
                        self.logger.warning(f"获取文件信息失败 {file_path}: {e}")
        
        backup_files.sort(key=lambda x: x[2], reverse=True)
        
        self.logger.info(f"扫描完成，共找到 {len(backup_files)} 个文件，总大小: {self._format_size(total_size)}")
        
        return [file_path for _, file_path, _ in backup_files]
    
    def _format_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.2f} {size_names[i]}"
    
    def create_full_backup(self):
        """创建全量备份"""
        try:
            self.logger.info("开始创建全量备份...")
            
            backup_files = self._get_backup_files()
            if not backup_files:
                self.logger.warning("没有找到需要备份的文件")
                return False
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_full_{timestamp}"
            
            if self.config["compression"]:
                archive_path = os.path.join(self.backup_root, f"{backup_name}.zip")
                self.logger.info(f"创建压缩备份: {archive_path}")
                
                with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in backup_files:
                        try:
                            rel_path = os.path.relpath(file_path, self.project_root)
                            zipf.write(file_path, rel_path)
                        except Exception as e:
                            self.logger.warning(f"添加文件到压缩包失败 {file_path}: {e}")
            else:
                # 创建目录备份
                archive_path = os.path.join(self.backup_root, backup_name)
                self.logger.info(f"创建目录备份: {archive_path}")
                
                for file_path in backup_files:
                    try:
                        rel_path = os.path.relpath(file_path, self.project_root)
                        target_path = os.path.join(archive_path, rel_path)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        shutil.copy2(file_path, target_path)
                    except Exception as e:
                        self.logger.warning(f"复制文件失败 {file_path}: {e}")
            
            self.logger.info(f"全量备份完成: {archive_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"创建全量备份失败: {e}")
            return False
    
    def list_backups(self):
        """列出所有备份"""
        try:
            if not os.path.exists(self.backup_root):
                self.logger.info("备份目录不存在")
                return
            
            backups = []
            for item in os.listdir(self.backup_root):
                item_path = os.path.join(self.backup_root, item)
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path)
                    mtime = os.path.getmtime(item_path)
                    backups.append((item, size, mtime))
                elif os.path.isdir(item_path):
                    size = self._get_dir_size(item_path)
                    mtime = os.path.getmtime(item_path)
                    backups.append((item, size, mtime))
            
            if not backups:
                self.logger.info("没有找到备份文件")
                return
            
            backups.sort(key=lambda x: x[2], reverse=True)
            
            self.logger.info(f"找到 {len(backups)} 个备份:")
            for i, (name, size, mtime) in enumerate(backups):
                timestamp = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                print(f"{i+1:2d}. {timestamp} - {self._format_size(size)} - {name}")
            
        except Exception as e:
            self.logger.error(f"列出备份失败: {e}")
    
    def _get_dir_size(self, dir_path):
        """获取目录大小"""
        total_size = 0
        try:
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):
                        total_size += os.path.getsize(file_path)
        except Exception:
            pass
        return total_size
    
    def cleanup_old_backups(self):
        """清理旧备份"""
        try:
            if not os.path.exists(self.backup_root):
                return True
            
            current_time = datetime.datetime.now()
            cleaned_count = 0
            
            for item in os.listdir(self.backup_root):
                item_path = os.path.join(self.backup_root, item)
                try:
                    mtime = os.path.getmtime(item_path)
                    item_time = datetime.datetime.fromtimestamp(mtime)
                    
                    if (current_time - item_time).days > self.config["retention_days"]:
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        
                        self.logger.info(f"已删除过期备份: {item}")
                        cleaned_count += 1
                        
                except Exception as e:
                    self.logger.warning(f"处理备份项失败 {item}: {e}")
            
            if cleaned_count > 0:
                self.logger.info(f"清理完成，删除了 {cleaned_count} 个过期备份")
            else:
                self.logger.info("没有需要清理的过期备份")
            
            return True
            
        except Exception as e:
            self.logger.error(f"清理旧备份失败: {e}")
            return False

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="系统程序全量备份脚本")
    parser.add_argument("--action", choices=["backup", "list", "cleanup"], 
                       default="backup", help="执行的操作")
    parser.add_argument("--project-root", help="项目根目录路径")
    
    args = parser.parse_args()
    
    # 创建备份管理器
    backup_manager = SystemBackup(args.project_root)
    
    try:
        if args.action == "backup":
            success = backup_manager.create_full_backup()
            if success:
                print("✅ 全量备份完成")
            else:
                print("❌ 全量备份失败")
                sys.exit(1)
        
        elif args.action == "list":
            backup_manager.list_backups()
        
        elif args.action == "cleanup":
            success = backup_manager.cleanup_old_backups()
            if success:
                print("✅ 旧备份清理完成")
            else:
                print("❌ 旧备份清理失败")
                sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
        sys.exit(1)
    
    except Exception as e:
        print(f"❌ 操作失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
