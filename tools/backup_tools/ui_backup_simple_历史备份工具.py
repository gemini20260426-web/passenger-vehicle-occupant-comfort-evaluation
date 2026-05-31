#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI重构项目简化备份脚本
将整个UI重构目录备份到E盘根目录，避免时间戳问题
"""

import os
import sys
import shutil
import zipfile
import json
import logging
import datetime
from pathlib import Path

class SimpleUIBackup:
    """UI重构项目简化备份管理器"""
    
    def __init__(self):
        # 设置项目根目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(os.path.dirname(script_dir))
        
        # 设置E盘备份目录
        self.backup_root = "E:\\UI重构备份"
        
        # 创建备份目录
        os.makedirs(self.backup_root, exist_ok=True)
        
        # 设置日志
        self._setup_logging()
        
        self.logger.info(f"UI重构简化备份管理器初始化完成")
        self.logger.info(f"项目根目录: {self.project_root}")
        self.logger.info(f"备份目标目录: {self.backup_root}")
    
    def _setup_logging(self):
        """设置日志系统"""
        log_dir = os.path.join(self.project_root, "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"ui_backup_simple_{datetime.datetime.now().strftime('%Y%m%d')}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def create_backup(self):
        """创建备份"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"UI重构_备份_{timestamp}"
            backup_path = os.path.join(self.backup_root, backup_name)
            
            self.logger.info(f"开始创建备份: {backup_name}")
            self.logger.info(f"备份路径: {backup_path}")
            
            # 创建备份目录
            os.makedirs(backup_path, exist_ok=True)
            
            # 统计信息
            total_files = 0
            copied_files = 0
            excluded_files = 0
            
            # 排除模式
            exclude_patterns = [
                "*.pyc", "__pycache__", "*.log", "*.tmp", "*.cache",
                ".git", ".vscode", "node_modules", "venv", "env",
                ".env", "*.bak", "backups", "temp", "logs",
                ".venv", "*.pkl", "*.zip", "*.tar.gz"
            ]
            
            # 遍历项目目录
            for root, dirs, files in os.walk(self.project_root):
                # 跳过排除的目录
                dirs[:] = [d for d in dirs if not any(pattern in d for pattern in exclude_patterns)]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    total_files += 1
                    
                    # 检查是否应该排除
                    should_exclude = False
                    for pattern in exclude_patterns:
                        if pattern.startswith("*."):
                            if file.endswith(pattern[1:]):
                                should_exclude = True
                                break
                        elif pattern in file:
                            should_exclude = True
                            break
                    
                    if should_exclude:
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
                        copied_files += 1
                        
                        if copied_files % 100 == 0:
                            self.logger.info(f"已复制 {copied_files} 个文件...")
                            
                    except Exception as e:
                        self.logger.warning(f"复制文件失败 {file_path}: {e}")
            
            # 创建压缩包
            zip_path = f"{backup_path}.zip"
            self.logger.info(f"开始创建压缩包: {zip_path}")
            
            try:
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
                    for root, dirs, files in os.walk(backup_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arc_name = os.path.relpath(file_path, backup_path)
                            
                            try:
                                # 使用当前时间作为文件时间，避免时间戳问题
                                zipf.write(file_path, arc_name)
                            except Exception as e:
                                self.logger.warning(f"添加文件到压缩包失败 {file_path}: {e}")
                                # 尝试读取文件内容并添加
                                try:
                                    with open(file_path, 'rb') as f:
                                        content = f.read()
                                    zipf.writestr(arc_name, content)
                                except Exception as e2:
                                    self.logger.error(f"无法添加文件到压缩包: {file_path}, 错误: {e2}")
                
                # 删除未压缩的备份目录
                shutil.rmtree(backup_path)
                backup_path = zip_path
                
                self.logger.info(f"压缩包创建完成: {zip_path}")
                
            except Exception as e:
                self.logger.error(f"创建压缩包失败: {e}")
                # 如果压缩失败，保留未压缩的备份
                self.logger.info(f"保留未压缩的备份目录: {backup_path}")
            
            # 输出统计信息
            self.logger.info("=" * 50)
            self.logger.info("备份完成统计:")
            self.logger.info(f"总文件数: {total_files}")
            self.logger.info(f"已复制文件: {copied_files}")
            self.logger.info(f"排除文件: {excluded_files}")
            self.logger.info(f"备份位置: {backup_path}")
            self.logger.info("=" * 50)
            
            return True
            
        except Exception as e:
            self.logger.error(f"创建备份失败: {e}")
            return False

def main():
    """主函数"""
    print("🚀 开始创建UI重构项目备份...")
    
    # 创建备份管理器
    backup_manager = SimpleUIBackup()
    
    try:
        success = backup_manager.create_backup()
        if success:
            print("✅ UI重构项目备份完成！")
            print(f"📁 备份位置: {backup_manager.backup_root}")
        else:
            print("❌ UI重构项目备份失败")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
        sys.exit(1)
    
    except Exception as e:
        print(f"❌ 操作失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
