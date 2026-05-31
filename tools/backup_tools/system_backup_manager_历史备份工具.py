#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统程序全量备份管理器
支持全量备份、增量备份、压缩、加密、自动清理等功能
"""

import os
import sys
import shutil
import zipfile
import tarfile
import hashlib
import json
import logging
import time
import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import argparse
import threading
import queue

class SystemBackupManager:
    """系统备份管理器"""
    
    def __init__(self, project_root: str = None):
        """初始化备份管理器"""
        self.project_root = project_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.backup_root = os.path.join(self.project_root, "backups")
        self.config_file = os.path.join(self.project_root, "backup_config.json")
        
        # 创建备份目录
        os.makedirs(self.backup_root, exist_ok=True)
        
        # 设置日志
        self._setup_logging()
        
        # 加载配置
        self.config = self._load_config()
        
        # 备份队列
        self.backup_queue = queue.Queue()
        self.backup_thread = None
        self.is_backing_up = False
        
        self.logger.info(f"系统备份管理器初始化完成，项目根目录: {self.project_root}")
    
    def _setup_logging(self):
        """设置日志系统"""
        log_dir = os.path.join(self.project_root, "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"backup_{datetime.datetime.now().strftime('%Y%m%d')}.log")
        
        # 配置日志格式
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def _load_config(self) -> Dict:
        """加载备份配置"""
        default_config = {
            "backup_types": {
                "full": {
                    "enabled": True,
                    "schedule": "daily",
                    "retention_days": 30,
                    "compression": True,
                    "encryption": False
                },
                "incremental": {
                    "enabled": True,
                    "schedule": "hourly",
                    "retention_days": 7,
                    "compression": True,
                    "encryption": False
                }
            },
            "exclude_patterns": [
                "*.pyc",
                "__pycache__",
                "*.log",
                "*.tmp",
                "*.cache",
                ".git",
                ".vscode",
                "node_modules",
                "venv",
                "env",
                ".env",
                "*.bak",
                "backups/*",
                "temp/*",
                "logs/*"
            ],
            "include_patterns": [
                "*.py",
                "*.md",
                "*.txt",
                "*.json",
                "*.xml",
                "*.yaml",
                "*.yml",
                "*.ini",
                "*.cfg",
                "*.conf",
                "*.html",
                "*.css",
                "*.js",
                "*.png",
                "*.jpg",
                "*.jpeg",
                "*.gif",
                "*.svg",
                "*.ico",
                "*.pdf",
                "*.doc",
                "*.docx",
                "*.xls",
                "*.xlsx",
                "*.ppt",
                "*.pptx"
            ],
            "compression_level": 6,
            "backup_name_format": "backup_{type}_{timestamp}_{hash}",
            "max_backup_size_gb": 10,
            "auto_cleanup": True
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # 合并用户配置和默认配置
                    default_config.update(user_config)
                    self.logger.info("已加载用户备份配置")
            except Exception as e:
                self.logger.warning(f"加载用户配置失败，使用默认配置: {e}")
        else:
            # 创建默认配置文件
            self._save_config(default_config)
            self.logger.info("已创建默认备份配置文件")
        
        return default_config
    
    def _save_config(self, config: Dict):
        """保存备份配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            self.logger.info("备份配置已保存")
        except Exception as e:
            self.logger.error(f"保存备份配置失败: {e}")
    
    def _get_file_hash(self, file_path: str) -> str:
        """计算文件哈希值"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.logger.warning(f"计算文件哈希失败 {file_path}: {e}")
            return ""
    
    def _should_backup_file(self, file_path: str) -> bool:
        """判断文件是否应该备份"""
        file_path = file_path.lower()
        
        # 检查排除模式
        for pattern in self.config["exclude_patterns"]:
            if self._match_pattern(file_path, pattern):
                return False
        
        # 检查包含模式
        for pattern in self.config["include_patterns"]:
            if self._match_pattern(file_path, pattern):
                return True
        
        return False
    
    def _match_pattern(self, file_path: str, pattern: str) -> bool:
        """匹配文件模式"""
        if "*" in pattern:
            # 通配符匹配
            import fnmatch
            return fnmatch.fnmatch(file_path, pattern)
        else:
            # 精确匹配
            return pattern in file_path
    
    def _get_backup_files(self) -> List[str]:
        """获取需要备份的文件列表"""
        backup_files = []
        total_size = 0
        
        self.logger.info("开始扫描需要备份的文件...")
        
        for root, dirs, files in os.walk(self.project_root):
            # 跳过备份目录本身
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
        
        # 按文件大小排序，大文件优先
        backup_files.sort(key=lambda x: x[2], reverse=True)
        
        self.logger.info(f"扫描完成，共找到 {len(backup_files)} 个文件，总大小: {self._format_size(total_size)}")
        
        return [file_path for _, file_path, _ in backup_files]
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.2f} {size_names[i]}"
    
    def _create_backup_archive(self, backup_files: List[str], backup_type: str, 
                              compression: bool = True) -> Tuple[str, str]:
        """创建备份压缩包"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{backup_type}_{timestamp}"
        
        if compression:
            archive_path = os.path.join(self.backup_root, f"{backup_name}.tar.gz")
            self.logger.info(f"创建压缩备份: {archive_path}")
            
            with tarfile.open(archive_path, "w:gz", compresslevel=self.config["compression_level"]) as tar:
                for file_path in backup_files:
                    try:
                        rel_path = os.path.relpath(file_path, self.project_root)
                        tar.add(file_path, arcname=rel_path)
                    except Exception as e:
                        self.logger.warning(f"添加文件到压缩包失败 {file_path}: {e}")
        else:
            archive_path = os.path.join(self.backup_root, f"{backup_name}.tar")
            self.logger.info(f"创建非压缩备份: {archive_path}")
            
            with tarfile.open(archive_path, "w") as tar:
                for file_path in backup_files:
                    try:
                        rel_path = os.path.relpath(file_path, self.project_root)
                        tar.add(file_path, arcname=rel_path)
                    except Exception as e:
                        self.logger.warning(f"添加文件到压缩包失败 {file_path}: {e}")
        
        # 计算备份包哈希值
        archive_hash = self._get_file_hash(archive_path)
        
        # 重命名文件，包含哈希值
        final_name = f"backup_{backup_type}_{timestamp}_{archive_hash[:8]}.tar.gz" if compression else f"backup_{backup_type}_{timestamp}_{archive_hash[:8]}.tar"
        final_path = os.path.join(self.backup_root, final_name)
        
        try:
            os.rename(archive_path, final_path)
            self.logger.info(f"备份文件已创建: {final_path}")
            return final_path, archive_hash
        except Exception as e:
            self.logger.error(f"重命名备份文件失败: {e}")
            return archive_path, archive_hash
    
    def _create_backup_manifest(self, backup_files: List[str], backup_type: str, 
                               archive_path: str, archive_hash: str) -> str:
        """创建备份清单文件"""
        manifest_data = {
            "backup_info": {
                "type": backup_type,
                "timestamp": datetime.datetime.now().isoformat(),
                "archive_path": archive_path,
                "archive_hash": archive_hash,
                "total_files": len(backup_files),
                "compression": archive_path.endswith('.gz')
            },
            "files": []
        }
        
        total_size = 0
        for file_path in backup_files:
            try:
                rel_path = os.path.relpath(file_path, self.project_root)
                file_size = os.path.getsize(file_path)
                file_hash = self._get_file_hash(file_path)
                total_size += file_size
                
                manifest_data["files"].append({
                    "path": rel_path,
                    "size": file_size,
                    "hash": file_hash,
                    "modified": datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                })
            except Exception as e:
                self.logger.warning(f"获取文件信息失败 {file_path}: {e}")
        
        manifest_data["backup_info"]["total_size"] = total_size
        
        # 保存清单文件
        manifest_path = archive_path.replace('.tar.gz', '.manifest.json').replace('.tar', '.manifest.json')
        try:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest_data, f, indent=4, ensure_ascii=False)
            self.logger.info(f"备份清单已创建: {manifest_path}")
            return manifest_path
        except Exception as e:
            self.logger.error(f"创建备份清单失败: {e}")
            return ""
    
    def create_full_backup(self, compression: bool = None) -> bool:
        """创建全量备份"""
        try:
            self.logger.info("开始创建全量备份...")
            
            # 获取需要备份的文件
            backup_files = self._get_backup_files()
            if not backup_files:
                self.logger.warning("没有找到需要备份的文件")
                return False
            
            # 使用配置中的压缩设置
            if compression is None:
                compression = self.config["backup_types"]["full"]["compression"]
            
            # 创建备份压缩包
            archive_path, archive_hash = self._create_backup_archive(backup_files, "full", compression)
            
            # 创建备份清单
            manifest_path = self._create_backup_manifest(backup_files, "full", archive_path, archive_hash)
            
            # 记录备份信息
            backup_info = {
                "type": "full",
                "timestamp": datetime.datetime.now().isoformat(),
                "archive_path": archive_path,
                "manifest_path": manifest_path,
                "archive_hash": archive_hash,
                "file_count": len(backup_files)
            }
            
            self._save_backup_record(backup_info)
            
            self.logger.info(f"全量备份完成: {archive_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"创建全量备份失败: {e}")
            return False
    
    def create_incremental_backup(self, compression: bool = None) -> bool:
        """创建增量备份"""
        try:
            self.logger.info("开始创建增量备份...")
            
            # 获取上次备份时间
            last_backup_time = self._get_last_backup_time()
            if not last_backup_time:
                self.logger.info("没有找到上次备份记录，创建全量备份")
                return self.create_full_backup(compression)
            
            # 获取需要备份的文件（修改时间在上次备份之后）
            backup_files = []
            for root, dirs, files in os.walk(self.project_root):
                if root.startswith(self.backup_root):
                    continue
                
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.project_root)
                    
                    if self._should_backup_file(rel_path):
                        try:
                            file_mtime = os.path.getmtime(file_path)
                            if file_mtime > last_backup_time:
                                backup_files.append(file_path)
                        except Exception as e:
                            self.logger.warning(f"获取文件修改时间失败 {file_path}: {e}")
            
            if not backup_files:
                self.logger.info("没有文件需要增量备份")
                return True
            
            # 使用配置中的压缩设置
            if compression is None:
                compression = self.config["backup_types"]["incremental"]["compression"]
            
            # 创建增量备份压缩包
            archive_path, archive_hash = self._create_backup_archive(backup_files, "incremental", compression)
            
            # 创建备份清单
            manifest_path = self._create_backup_manifest(backup_files, "incremental", archive_path, archive_hash)
            
            # 记录备份信息
            backup_info = {
                "type": "incremental",
                "timestamp": datetime.datetime.now().isoformat(),
                "archive_path": archive_path,
                "manifest_path": manifest_path,
                "archive_hash": archive_hash,
                "file_count": len(backup_files)
            }
            
            self._save_backup_record(backup_info)
            
            self.logger.info(f"增量备份完成: {archive_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"创建增量备份失败: {e}")
            return False
    
    def _get_last_backup_time(self) -> Optional[float]:
        """获取上次备份时间"""
        try:
            backup_records = self._load_backup_records()
            if not backup_records:
                return None
            
            # 按时间排序，获取最新的备份
            latest_backup = max(backup_records, key=lambda x: x.get("timestamp", ""))
            return datetime.datetime.fromisoformat(latest_backup["timestamp"]).timestamp()
            
        except Exception as e:
            self.logger.warning(f"获取上次备份时间失败: {e}")
            return None
    
    def _save_backup_record(self, backup_info: Dict):
        """保存备份记录"""
        try:
            records_file = os.path.join(self.backup_root, "backup_records.json")
            records = []
            
            if os.path.exists(records_file):
                with open(records_file, 'r', encoding='utf-8') as f:
                    records = json.load(f)
            
            records.append(backup_info)
            
            with open(records_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            self.logger.warning(f"保存备份记录失败: {e}")
    
    def _load_backup_records(self) -> List[Dict]:
        """加载备份记录"""
        try:
            records_file = os.path.join(self.backup_root, "backup_records.json")
            if not os.path.exists(records_file):
                return []
            
            with open(records_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            self.logger.warning(f"加载备份记录失败: {e}")
            return []
    
    def list_backups(self) -> List[Dict]:
        """列出所有备份"""
        try:
            records = self._load_backup_records()
            if not records:
                self.logger.info("没有找到备份记录")
                return []
            
            # 按时间排序
            records.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            self.logger.info(f"找到 {len(records)} 个备份:")
            for i, record in enumerate(records):
                timestamp = record.get("timestamp", "")
                backup_type = record.get("type", "unknown")
                file_count = record.get("file_count", 0)
                archive_path = record.get("archive_path", "")
                
                print(f"{i+1:2d}. [{backup_type.upper():10s}] {timestamp[:19]} - {file_count:4d} 文件 - {os.path.basename(archive_path)}")
            
            return records
            
        except Exception as e:
            self.logger.error(f"列出备份失败: {e}")
            return []
    
    def restore_backup(self, backup_index: int) -> bool:
        """恢复指定备份"""
        try:
            records = self._load_backup_records()
            if not records or backup_index < 0 or backup_index >= len(records):
                self.logger.error(f"无效的备份索引: {backup_index}")
                return False
            
            backup_record = records[backup_index]
            archive_path = backup_record.get("archive_path", "")
            
            if not os.path.exists(archive_path):
                self.logger.error(f"备份文件不存在: {archive_path}")
                return False
            
            self.logger.info(f"开始恢复备份: {archive_path}")
            
            # 创建恢复目录
            restore_dir = os.path.join(self.backup_root, f"restore_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(restore_dir, exist_ok=True)
            
            # 解压备份文件
            if archive_path.endswith('.gz'):
                with tarfile.open(archive_path, 'r:gz') as tar:
                    tar.extractall(restore_dir)
            else:
                with tarfile.open(archive_path, 'r') as tar:
                    tar.extractall(restore_dir)
            
            self.logger.info(f"备份已解压到: {restore_dir}")
            self.logger.info("请手动将文件复制到目标位置")
            
            return True
            
        except Exception as e:
            self.logger.error(f"恢复备份失败: {e}")
            return False
    
    def cleanup_old_backups(self) -> bool:
        """清理旧备份"""
        try:
            if not self.config.get("auto_cleanup", True):
                self.logger.info("自动清理已禁用")
                return True
            
            self.logger.info("开始清理旧备份...")
            
            records = self._load_backup_records()
            if not records:
                return True
            
            current_time = datetime.datetime.now()
            cleaned_count = 0
            
            for record in records:
                try:
                    timestamp_str = record.get("timestamp", "")
                    if not timestamp_str:
                        continue
                    
                    backup_time = datetime.datetime.fromisoformat(timestamp_str)
                    backup_type = record.get("type", "unknown")
                    
                    # 获取保留天数
                    retention_days = self.config["backup_types"].get(backup_type, {}).get("retention_days", 30)
                    
                    if (current_time - backup_time).days > retention_days:
                        archive_path = record.get("archive_path", "")
                        manifest_path = record.get("manifest_path", "")
                        
                        # 删除备份文件
                        if os.path.exists(archive_path):
                            os.remove(archive_path)
                            self.logger.info(f"已删除过期备份: {archive_path}")
                        
                        if manifest_path and os.path.exists(manifest_path):
                            os.remove(manifest_path)
                        
                        cleaned_count += 1
                        
                except Exception as e:
                    self.logger.warning(f"处理备份记录失败: {e}")
            
            if cleaned_count > 0:
                # 重新保存清理后的记录
                active_records = [r for r in records if r not in records[:cleaned_count]]
                self._save_clean_backup_records(active_records)
                self.logger.info(f"清理完成，删除了 {cleaned_count} 个过期备份")
            else:
                self.logger.info("没有需要清理的过期备份")
            
            return True
            
        except Exception as e:
            self.logger.error(f"清理旧备份失败: {e}")
            return False
    
    def _save_clean_backup_records(self, records: List[Dict]):
        """保存清理后的备份记录"""
        try:
            records_file = os.path.join(self.backup_root, "backup_records.json")
            with open(records_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.logger.warning(f"保存清理后的备份记录失败: {e}")
    
    def get_backup_status(self) -> Dict:
        """获取备份状态"""
        try:
            records = self._load_backup_records()
            
            status = {
                "total_backups": len(records),
                "full_backups": len([r for r in records if r.get("type") == "full"]),
                "incremental_backups": len([r for r in records if r.get("type") == "incremental"]),
                "last_backup": None,
                "backup_size": 0,
                "available_space": 0
            }
            
            if records:
                # 获取最新备份时间
                latest_backup = max(records, key=lambda x: x.get("timestamp", ""))
                status["last_backup"] = latest_backup.get("timestamp", "")
                
                # 计算备份总大小
                for record in records:
                    archive_path = record.get("archive_path", "")
                    if os.path.exists(archive_path):
                        status["backup_size"] += os.path.getsize(archive_path)
            
            # 获取可用空间
            try:
                statvfs = os.statvfs(self.backup_root)
                status["available_space"] = statvfs.f_frsize * statvfs.f_bavail
            except:
                status["available_space"] = 0
            
            return status
            
        except Exception as e:
            self.logger.error(f"获取备份状态失败: {e}")
            return {}
    
    def start_background_backup(self, backup_type: str = "full"):
        """启动后台备份"""
        if self.is_backing_up:
            self.logger.warning("备份任务已在运行中")
            return False
        
        self.is_backing_up = True
        self.backup_thread = threading.Thread(target=self._background_backup_worker, args=(backup_type,))
        self.backup_thread.daemon = True
        self.backup_thread.start()
        
        self.logger.info(f"后台{backup_type}备份已启动")
        return True
    
    def _background_backup_worker(self, backup_type: str):
        """后台备份工作线程"""
        try:
            if backup_type == "full":
                self.create_full_backup()
            elif backup_type == "incremental":
                self.create_incremental_backup()
            else:
                self.logger.error(f"不支持的备份类型: {backup_type}")
        except Exception as e:
            self.logger.error(f"后台备份失败: {e}")
        finally:
            self.is_backing_up = False
    
    def stop_background_backup(self):
        """停止后台备份"""
        if self.backup_thread and self.backup_thread.is_alive():
            self.is_backing_up = False
            self.backup_thread.join(timeout=5)
            self.logger.info("后台备份已停止")
        else:
            self.logger.info("没有运行中的后台备份任务")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="系统程序全量备份管理器")
    parser.add_argument("--action", choices=["full", "incremental", "list", "restore", "cleanup", "status"], 
                       default="full", help="执行的操作")
    parser.add_argument("--restore-index", type=int, help="恢复备份的索引（用于restore操作）")
    parser.add_argument("--background", action="store_true", help="在后台运行备份")
    parser.add_argument("--no-compression", action="store_true", help="禁用压缩")
    parser.add_argument("--config", help="配置文件路径")
    
    args = parser.parse_args()
    
    # 创建备份管理器
    backup_manager = SystemBackupManager()
    
    try:
        if args.action == "full":
            if args.background:
                backup_manager.start_background_backup("full")
            else:
                success = backup_manager.create_full_backup(not args.no_compression)
                if success:
                    print("✅ 全量备份完成")
                else:
                    print("❌ 全量备份失败")
                    sys.exit(1)
        
        elif args.action == "incremental":
            if args.background:
                backup_manager.start_background_backup("incremental")
            else:
                success = backup_manager.create_incremental_backup(not args.no_compression)
                if success:
                    print("✅ 增量备份完成")
                else:
                    print("❌ 增量备份失败")
                    sys.exit(1)
        
        elif args.action == "list":
            backup_manager.list_backups()
        
        elif args.action == "restore":
            if args.restore_index is None:
                print("❌ 请指定要恢复的备份索引 (--restore-index)")
                sys.exit(1)
            
            success = backup_manager.restore_backup(args.restore_index)
            if success:
                print("✅ 备份恢复完成")
            else:
                print("❌ 备份恢复失败")
                sys.exit(1)
        
        elif args.action == "cleanup":
            success = backup_manager.cleanup_old_backups()
            if success:
                print("✅ 旧备份清理完成")
            else:
                print("❌ 旧备份清理失败")
                sys.exit(1)
        
        elif args.action == "status":
            status = backup_manager.get_backup_status()
            print("\n📊 备份状态:")
            print(f"   总备份数: {status.get('total_backups', 0)}")
            print(f"   全量备份: {status.get('full_backups', 0)}")
            print(f"   增量备份: {status.get('incremental_backups', 0)}")
            print(f"   最后备份: {status.get('last_backup', '无')}")
            print(f"   备份大小: {backup_manager._format_size(status.get('backup_size', 0))}")
            print(f"   可用空间: {backup_manager._format_size(status.get('available_space', 0))}")
        
        # 等待后台任务完成
        if args.background and backup_manager.is_backing_up:
            print("🔄 后台备份任务已启动，请等待完成...")
            while backup_manager.is_backing_up:
                time.sleep(1)
            print("✅ 后台备份任务完成")
    
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
        if backup_manager.is_backing_up:
            backup_manager.stop_background_backup()
        sys.exit(1)
    
    except Exception as e:
        print(f"❌ 操作失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
