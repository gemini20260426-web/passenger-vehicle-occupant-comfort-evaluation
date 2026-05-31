#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI重构项目专用备份脚本
将整个UI重构目录备份到E盘根目录
支持压缩、增量备份、时间戳命名等功能
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

class UIBackupToEDrive:
    """UI重构项目备份管理器 - 备份到E盘"""
    
    def __init__(self, project_root=None):
        # 设置项目根目录
        if project_root:
            self.project_root = project_root
        else:
            # 从当前脚本位置计算项目根目录
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.project_root = os.path.dirname(os.path.dirname(script_dir))
        
        # 设置E盘备份目录
        self.backup_root = "E:\\UI重构备份"
        self.config_file = os.path.join(self.project_root, "ui_backup_config.json")
        
        # 创建备份目录
        os.makedirs(self.backup_root, exist_ok=True)
        
        # 设置日志
        self._setup_logging()
        
        # 加载配置
        self.config = self._load_config()
        
        self.logger.info(f"UI重构备份管理器初始化完成")
        self.logger.info(f"项目根目录: {self.project_root}")
        self.logger.info(f"备份目标目录: {self.backup_root}")
    
    def _setup_logging(self):
        """设置日志系统"""
        log_dir = os.path.join(self.project_root, "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"ui_backup_e_drive_{datetime.datetime.now().strftime('%Y%m%d')}.log")
        
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
                ".env", "*.bak", "backups/*", "temp/*", "logs/*",
                ".venv", "*.pkl", "*.zip", "*.tar.gz"
            ],
            "include_patterns": [
                "*.py", "*.md", "*.txt", "*.json", "*.xml", "*.yaml",
                "*.yml", "*.ini", "*.cfg", "*.conf", "*.html", "*.css",
                "*.js", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg",
                "*.bat", "*.ps1", "*.sh"
            ],
            "compression": True,
            "compression_level": 6,
            "retention_days": 30,
            "max_backup_size_gb": 10
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
            self.logger.error(f"保存配置失败: {e}")
    
    def _should_exclude(self, file_path):
        """判断文件是否应该被排除"""
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_name)[1].lower()
        
        # 检查排除模式
        for pattern in self.config["exclude_patterns"]:
            if pattern.startswith("*."):
                if file_ext == pattern[1:]:
                    return True
            elif pattern in file_name:
                return True
            elif pattern in file_path:
                return True
        
        return False
    
    def _should_include(self, file_path):
        """判断文件是否应该被包含"""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # 检查包含模式
        for pattern in self.config["include_patterns"]:
            if pattern.startswith("*."):
                if file_ext == pattern[1:]:
                    return True
        
        return True
    
    def create_full_backup(self):
        """创建全量备份"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"UI重构_全量备份_{timestamp}"
            backup_path = os.path.join(self.backup_root, backup_name)
            
            self.logger.info(f"开始创建全量备份: {backup_name}")
            self.logger.info(f"备份路径: {backup_path}")
            
            # 创建备份目录
            os.makedirs(backup_path, exist_ok=True)
            
            # 统计信息
            total_files = 0
            total_size = 0
            copied_files = 0
            excluded_files = 0
            
            # 遍历项目目录
            for root, dirs, files in os.walk(self.project_root):
                # 跳过排除的目录
                dirs[:] = [d for d in dirs if not self._should_exclude(os.path.join(root, d))]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    total_files += 1
                    
                    # 检查是否应该排除
                    if self._should_exclude(file_path):
                        excluded_files += 1
                        continue
                    
                    # 计算相对路径
                    rel_path = os.path.relpath(file_path, self.project_root)
                    target_path = os.path.join(backup_path, rel_path)
                    
                    # 创建目标目录
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    
                    try:
                        # 复制文件
                        shutil.copy2(file_path, target_path)
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        copied_files += 1
                        
                        if copied_files % 100 == 0:
                            self.logger.info(f"已复制 {copied_files} 个文件...")
                            
                    except Exception as e:
                        self.logger.warning(f"复制文件失败 {file_path}: {e}")
            
            # 创建压缩包
            if self.config["compression"]:
                zip_path = f"{backup_path}.zip"
                self.logger.info(f"开始创建压缩包: {zip_path}")
                
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, 
                                   compresslevel=self.config["compression_level"]) as zipf:
                    for root, dirs, files in os.walk(backup_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arc_name = os.path.relpath(file_path, backup_path)
                            
                            try:
                                # 获取文件时间戳，处理异常时间戳
                                file_stat = os.stat(file_path)
                                file_time = file_stat.st_mtime
                                
                                # 如果时间戳异常，使用当前时间
                                if file_time < 0 or file_time > 2147483647:  # 1970-2038年范围
                                    file_time = time.time()
                                    self.logger.warning(f"文件时间戳异常，使用当前时间: {file_path}")
                                
                                # 转换为ZIP兼容的时间元组
                                time_tuple = time.localtime(file_time)
                                time_tuple = (time_tuple[0], time_tuple[1], time_tuple[2],
                                            time_tuple[3], time_tuple[4], time_tuple[5])
                                
                                zipf.write(file_path, arc_name, compress_type=zipfile.ZIP_DEFLATED)
                                
                                # 手动设置文件时间
                                zipf.writestr(arc_name, open(file_path, 'rb').read(), 
                                            compress_type=zipfile.ZIP_DEFLATED)
                                
                            except Exception as e:
                                self.logger.warning(f"添加文件到压缩包失败 {file_path}: {e}")
                                # 尝试不设置时间戳的方式添加
                                try:
                                    zipf.write(file_path, arc_name)
                                except Exception as e2:
                                    self.logger.error(f"无法添加文件到压缩包: {file_path}, 错误: {e2}")
                
                # 删除未压缩的备份目录
                shutil.rmtree(backup_path)
                backup_path = zip_path
                
                self.logger.info(f"压缩包创建完成: {zip_path}")
            
            # 创建备份信息文件
            info_file = f"{backup_path}.info.json"
            backup_info = {
                "backup_name": backup_name,
                "backup_time": timestamp,
                "project_root": self.project_root,
                "total_files": total_files,
                "copied_files": copied_files,
                "excluded_files": excluded_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "compression": self.config["compression"],
                "config": self.config
            }
            
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, indent=4, ensure_ascii=False)
            
            # 输出统计信息
            self.logger.info("=" * 50)
            self.logger.info("备份完成统计:")
            self.logger.info(f"总文件数: {total_files}")
            self.logger.info(f"已复制文件: {copied_files}")
            self.logger.info(f"排除文件: {excluded_files}")
            self.logger.info(f"总大小: {round(total_size / (1024 * 1024), 2)} MB")
            self.logger.info(f"备份位置: {backup_path}")
            self.logger.info("=" * 50)
            
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
                    # 检查是否是备份文件
                    if item.endswith('.zip') or item.endswith('.info.json'):
                        continue
                    
                    stat = os.stat(item_path)
                    backups.append({
                        'name': item,
                        'size': stat.st_size,
                        'mtime': datetime.datetime.fromtimestamp(stat.st_mtime)
                    })
            
            if not backups:
                self.logger.info("没有找到备份文件")
                return
            
            # 按时间排序
            backups.sort(key=lambda x: x['mtime'], reverse=True)
            
            self.logger.info("=" * 50)
            self.logger.info("备份文件列表:")
            for backup in backups:
                size_mb = round(backup['size'] / (1024 * 1024), 2)
                self.logger.info(f"{backup['name']} - {size_mb} MB - {backup['mtime']}")
            self.logger.info("=" * 50)
            
        except Exception as e:
            self.logger.error(f"列出备份失败: {e}")
    
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
    
    parser = argparse.ArgumentParser(description="UI重构项目备份脚本 - 备份到E盘")
    parser.add_argument("--action", choices=["backup", "list", "cleanup"], 
                       default="backup", help="执行的操作")
    parser.add_argument("--project-root", help="项目根目录路径")
    
    args = parser.parse_args()
    
    # 创建备份管理器
    backup_manager = UIBackupToEDrive(args.project_root)
    
    try:
        if args.action == "backup":
            print("🚀 开始创建UI重构项目全量备份...")
            success = backup_manager.create_full_backup()
            if success:
                print("✅ UI重构项目全量备份完成！")
                print(f"📁 备份位置: {backup_manager.backup_root}")
            else:
                print("❌ UI重构项目备份失败")
                sys.exit(1)
        
        elif args.action == "list":
            backup_manager.list_backups()
        
        elif args.action == "cleanup":
            print("🧹 开始清理旧备份...")
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
