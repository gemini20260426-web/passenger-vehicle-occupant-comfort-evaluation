"""自动报告生成调度器（定时生成驾驶行为分析报告）"""
import logging
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from PySide6.QtCore import QObject, Signal, Slot, QThread, QMutex, QMutexLocker, QTimer

class ReportScheduler(QObject):
    """自动报告生成调度器（保持原有类名）"""
    # 信号定义（新增状态通知机制）
    report_generated = Signal(str, str)  # 报告类型, 报告路径
    report_failed = Signal(str, str)     # 报告类型, 错误信息
    schedule_updated = Signal(dict)      # 调度计划更新
    progress_updated = Signal(str, int)  # 报告类型, 进度(0-100)

    def __init__(self, report_generator, storage_manager):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.report_generator = report_generator  # 报告生成器实例
        self.storage_manager = storage_manager    # 存储管理器实例
        
        # 线程安全锁（新增）
        self.scheduler_lock = QMutex()
        
        # 调度配置（保持原有）
        self.schedule_config = {
            'daily': {
                'enabled': True,
                'time': '23:59',  # 每日生成时间
                'last_run': 0     # 上次运行时间戳
            },
            'weekly': {
                'enabled': True,
                'day': 0,         # 0=周一, 6=周日
                'time': '23:59',  # 每周生成时间
                'last_run': 0     # 上次运行时间戳
            },
            'monthly': {
                'enabled': True,
                'date': 1,        # 每月1日
                'time': '23:59',  # 每月生成时间
                'last_run': 0     # 上次运行时间戳
            },
            'output_dir': 'reports',  # 报告输出目录
            'format': 'pdf',          # 报告格式: pdf, html, csv
            'keep_reports': 30        # 保留报告天数
        }
        
        # 报告生成线程（新增）
        self.generator_threads = {}  # 按报告类型存储线程
        
        # 初始化（保持原有方法）
        self._init_report_dir()
        self._load_schedule_config()
        
        # 启动调度器（新增）
        self._start_scheduler()

    def _init_report_dir(self) -> None:
        """初始化报告目录（保持原有方法）"""
        try:
            os.makedirs(self.schedule_config['output_dir'], exist_ok=True)
            self.logger.info(f"报告目录已初始化: {self.schedule_config['output_dir']}")
        except Exception as e:
            self.logger.error(f"初始化报告目录失败: {str(e)}")
            raise

    def _load_schedule_config(self) -> None:
        """加载调度配置（保持原有方法）"""
        config_path = os.path.join(self.schedule_config['output_dir'], 'report_schedule.json')
        if os.path.exists(config_path):
            try:
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                
                # 合并配置
                with QMutexLocker(self.scheduler_lock):
                    self._merge_config(self.schedule_config, saved_config)
                
                self.logger.info("报告调度配置已加载")
                
            except Exception as e:
                self.logger.error(f"加载报告调度配置失败: {str(e)}")

    def _merge_config(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """合并配置（递归）（保持原有方法）"""
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._merge_config(target[key], value)
            else:
                target[key] = value

    def _save_schedule_config(self) -> None:
        """保存调度配置（保持原有方法）"""
        config_path = os.path.join(self.schedule_config['output_dir'], 'report_schedule.json')
        try:
            import json
            with QMutexLocker(self.scheduler_lock):
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.schedule_config, f, ensure_ascii=False, indent=4)
            self.logger.info("报告调度配置已保存")
        except Exception as e:
            self.logger.error(f"保存报告调度配置失败: {str(e)}")

    def get_schedule_config(self) -> Dict[str, Any]:
        """获取调度配置（线程安全）"""
        with QMutexLocker(self.scheduler_lock):
            return self.schedule_config.copy()

    def set_schedule_config(self, config: Dict[str, Any]) -> None:
        """设置调度配置（线程安全）"""
        with QMutexLocker(self.scheduler_lock):
            self._merge_config(self.schedule_config, config)
        
        # 保存配置
        self._save_schedule_config()
        
        # 重启调度器
        self._restart_scheduler()
        
        # 发射配置更新信号
        self.schedule_updated.emit(self.get_schedule_config())
        
        self.logger.info("报告调度配置已更新")

    def _start_scheduler(self) -> None:
        """启动调度器（新增）"""
        # 创建定时器，每分钟检查一次是否需要生成报告
        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self._check_schedule)
        self.scheduler_timer.start(60000)  # 60秒 = 1分钟
        
        self.logger.info("报告调度器已启动")
        
        # 立即检查一次
        QTimer.singleShot(1000, self._check_schedule)

    def _restart_scheduler(self) -> None:
        """重启调度器（新增）"""
        if hasattr(self, 'scheduler_timer'):
            self.scheduler_timer.stop()
        
        self._start_scheduler()

    @Slot()
    def _check_schedule(self) -> None:
        """检查调度计划，判断是否需要生成报告（新增）"""
        current_time = time.time()
        current_dt = datetime.now()
        
        with QMutexLocker(self.scheduler_lock):
            # 检查每日报告
            if self.schedule_config['daily']['enabled']:
                if self._should_run_daily(current_time, current_dt):
                    self.generate_daily_report()
            
            # 检查每周报告
            if self.schedule_config['weekly']['enabled']:
                if self._should_run_weekly(current_time, current_dt):
                    self.generate_weekly_report()
            
            # 检查每月报告
            if self.schedule_config['monthly']['enabled']:
                if self._should_run_monthly(current_time, current_dt):
                    self.generate_monthly_report()
        
        # 清理过期报告
        self._cleanup_old_reports()

    def _should_run_daily(self, current_time: float, current_dt: datetime) -> bool:
        """判断是否应该生成每日报告（新增）"""
        # 检查是否已超过上次运行时间至少一天
        last_run = self.schedule_config['daily']['last_run']
        if current_time - last_run < 86400:  # 86400秒 = 24小时
            return False
            
        # 检查是否达到设定时间
        try:
            hour, minute = map(int, self.schedule_config['daily']['time'].split(':'))
            target_time = current_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            target_timestamp = target_time.timestamp()
            
            # 如果当前时间已过今日目标时间，且未超过明日凌晨2点
            return (current_time >= target_timestamp and 
                    current_time < target_timestamp + 7200)  # 7200秒 = 2小时容错
            
        except Exception as e:
            self.logger.error(f"解析每日报告时间失败: {str(e)}")
            return False

    def _should_run_weekly(self, current_time: float, current_dt: datetime) -> bool:
        """判断是否应该生成每周报告（新增）"""
        # 检查是否已超过上次运行时间至少一周
        last_run = self.schedule_config['weekly']['last_run']
        if current_time - last_run < 604800:  # 604800秒 = 7天
            return False
            
        # 检查是否是设定的星期几
        if current_dt.weekday() != self.schedule_config['weekly']['day']:
            return False
            
        # 检查是否达到设定时间
        try:
            hour, minute = map(int, self.schedule_config['weekly']['time'].split(':'))
            target_time = current_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            target_timestamp = target_time.timestamp()
            
            # 如果当前时间已过目标时间，且未超过凌晨2点
            return (current_time >= target_timestamp and 
                    current_time < target_timestamp + 7200)  # 7200秒 = 2小时容错
            
        except Exception as e:
            self.logger.error(f"解析每周报告时间失败: {str(e)}")
            return False

    def _should_run_monthly(self, current_time: float, current_dt: datetime) -> bool:
        """判断是否应该生成每月报告（新增）"""
        # 检查是否已超过上次运行时间至少一个月
        last_run = self.schedule_config['monthly']['last_run']
        if current_time - last_run < 2592000:  # 2592000秒 = 30天
            return False
            
        # 检查是否是设定的日期（考虑当月最后一天）
        target_date = self.schedule_config['monthly']['date']
        last_day = (current_dt.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        if current_dt.day != min(target_date, last_day.day):
            return False
            
        # 检查是否达到设定时间
        try:
            hour, minute = map(int, self.schedule_config['monthly']['time'].split(':'))
            target_time = current_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            target_timestamp = target_time.timestamp()
            
            # 如果当前时间已过目标时间，且未超过凌晨2点
            return (current_time >= target_timestamp and 
                    current_time < target_timestamp + 7200)  # 7200秒 = 2小时容错
            
        except Exception as e:
            self.logger.error(f"解析每月报告时间失败: {str(e)}")
            return False

    def generate_daily_report(self, date: Optional[datetime] = None) -> bool:
        """生成每日报告（线程安全）"""
        return self._generate_report('daily', date)

    def generate_weekly_report(self, end_date: Optional[datetime] = None) -> bool:
        """生成每周报告（线程安全）"""
        return self._generate_report('weekly', end_date)

    def generate_monthly_report(self, end_date: Optional[datetime] = None) -> bool:
        """生成每月报告（线程安全）"""
        return self._generate_report('monthly', end_date)

    def _generate_report(self, report_type: str, end_date: Optional[datetime] = None) -> bool:
        """生成报告（线程安全实现）"""
        # 检查是否已有相同类型的报告正在生成
        with QMutexLocker(self.scheduler_lock):
            if report_type in self.generator_threads and self.generator_threads[report_type].isRunning():
                self.logger.warning(f"已有{report_type}报告生成任务在运行，无法创建新任务")
                return False
        
        # 确定日期范围
        if not end_date:
            end_date = datetime.now()
        
        if report_type == 'daily':
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            period_desc = start_date.strftime("%Y%m%d")
        elif report_type == 'weekly':
            start_date = end_date - timedelta(days=end_date.weekday() + 1)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            period_desc = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        elif report_type == 'monthly':
            start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_desc = start_date.strftime("%Y%m")
        else:
            self.logger.error(f"不支持的报告类型: {report_type}")
            return False
        
        # 创建报告生成线程
        thread = ReportGeneratorThread(
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            output_dir=self.schedule_config['output_dir'],
            format=self.schedule_config['format'],
            report_generator=self.report_generator,
            storage_manager=self.storage_manager
        )
        
        # 连接信号
        thread.progress_updated.connect(self._on_report_progress)
        thread.task_completed.connect(lambda success, path, msg: 
                                     self._on_report_completed(report_type, success, path, msg, time.time()))
        
        # 保存线程引用
        with QMutexLocker(self.scheduler_lock):
            self.generator_threads[report_type] = thread
        
        # 启动线程
        thread.start()
        self.logger.info(f"开始生成{report_type}报告: {period_desc}")
        return True

    @Slot(str, int)
    def _on_report_progress(self, report_type: str, progress: int) -> None:
        """处理报告生成进度更新（新增）"""
        self.progress_updated.emit(report_type, progress)

    @Slot(str, bool, str, str, float)
    def _on_report_completed(self, report_type: str, success: bool, path: str, message: str, timestamp: float) -> None:
        """处理报告生成完成（新增）"""
        # 更新上次运行时间
        with QMutexLocker(self.scheduler_lock):
            # 移除线程引用
            if report_type in self.generator_threads:
                del self.generator_threads[report_type]
                
            # 更新最后运行时间
            if success and report_type in self.schedule_config:
                self.schedule_config[report_type]['last_run'] = timestamp
                self._save_schedule_config()
        
        # 发射完成信号
        if success:
            self.logger.info(f"{report_type}报告生成成功: {path}")
            self.report_generated.emit(report_type, path)
        else:
            self.logger.error(f"{report_type}报告生成失败: {message}")
            self.report_failed.emit(report_type, message)

    def _cleanup_old_reports(self) -> None:
        """清理过期报告（新增）"""
        try:
            keep_days = self.schedule_config['keep_reports']
            if keep_days <= 0:
                return
                
            cutoff_time = time.time() - (keep_days * 86400)  # 转换为秒
            deleted_count = 0
            
            # 遍历报告目录
            for filename in os.listdir(self.schedule_config['output_dir']):
                # 只处理报告文件
                if not (filename.startswith('daily_') or 
                        filename.startswith('weekly_') or 
                        filename.startswith('monthly_')):
                    continue
                    
                file_path = os.path.join(self.schedule_config['output_dir'], filename)
                
                # 检查文件修改时间
                if os.path.getmtime(file_path) < cutoff_time:
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                    except Exception as e:
                        self.logger.warning(f"删除过期报告失败 {filename}: {str(e)}")
            
            if deleted_count > 0:
                self.logger.info(f"已清理 {deleted_count} 个过期报告")
                
        except Exception as e:
            self.logger.error(f"清理过期报告失败: {str(e)}")

    def get_recent_reports(self, count: int = 10) -> List[Dict[str, Any]]:
        """获取最近的报告列表（新增）"""
        reports = []
        
        try:
            # 遍历报告目录
            for filename in os.listdir(self.schedule_config['output_dir']):
                # 只处理报告文件
                if filename.startswith('daily_'):
                    report_type = 'daily'
                elif filename.startswith('weekly_'):
                    report_type = 'weekly'
                elif filename.startswith('monthly_'):
                    report_type = 'monthly'
                else:
                    continue
                    
                file_path = os.path.join(self.schedule_config['output_dir'], filename)
                
                # 获取文件信息
                file_size = os.path.getsize(file_path)
                modify_time = os.path.getmtime(file_path)
                
                reports.append({
                    'filename': filename,
                    'type': report_type,
                    'path': file_path,
                    'size': file_size,
                    'size_str': self._format_file_size(file_size),
                    'modify_time': modify_time,
                    'modify_time_str': datetime.fromtimestamp(modify_time).strftime("%Y-%m-%d %H:%M:%S")
                })
            
            # 按修改时间排序（最新的在前）
            reports.sort(key=lambda x: x['modify_time'], reverse=True)
            
        except Exception as e:
            self.logger.error(f"获取报告列表失败: {str(e)}")
        
        # 返回指定数量的最近报告
        return reports[:count]

    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小（复用原有方法）"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


class ReportGeneratorThread(QThread):
    """报告生成线程（新增，处理实际报告生成工作）"""
    progress_updated = Signal(str, int)  # 报告类型, 进度
    task_completed = Signal(bool, str, str)  # 成功标志, 报告路径, 消息

    def __init__(self, report_type: str, start_date: datetime, end_date: datetime,
                 output_dir: str, format: str, report_generator, storage_manager):
        super().__init__()
        self.report_type = report_type
        self.start_date = start_date
        self.end_date = end_date
        self.output_dir = output_dir
        self.format = format.lower()
        self.report_generator = report_generator
        self.storage_manager = storage_manager

    def run(self) -> None:
        """执行报告生成任务"""
        try:
            # 报告类型描述
            type_desc = {
                'daily': '每日',
                'weekly': '每周',
                'monthly': '每月'
            }.get(self.report_type, self.report_type)
            
            # 发送开始进度
            self.progress_updated.emit(self.report_type, 10)
            
            # 1. 收集数据
            self.progress_updated.emit(self.report_type, 20)
            self.progress_updated.emit(self.report_type, f"正在收集{type_desc}数据...")
            
            # 获取指定时间段的驾驶行为数据
            behavior_data = self.storage_manager.get_behavior_data(
                start_time=self.start_date.timestamp(),
                end_time=self.end_date.timestamp()
            )
            
            if not behavior_data:
                self.task_completed.emit(
                    False, "", f"没有找到{type_desc}的数据，无法生成报告"
                )
                return
            
            # 2. 生成报告内容
            self.progress_updated.emit(self.report_type, 40)
            self.progress_updated.emit(self.report_type, f"正在生成{type_desc}报告内容...")
            
            report_data = self.report_generator.generate_report_data(
                data=behavior_data,
                start_date=self.start_date,
                end_date=self.end_date,
                report_type=self.report_type
            )
            
            # 3. 生成报告文件
            self.progress_updated.emit(self.report_type, 60)
            self.progress_updated.emit(self.report_type, f"正在生成{type_desc}报告文件...")
            
            # 生成文件名
            if self.report_type == 'daily':
                filename = f"daily_{self.start_date.strftime('%Y%m%d')}.{self.format}"
            elif self.report_type == 'weekly':
                filename = f"weekly_{self.start_date.strftime('%Y%m%d')}_{self.end_date.strftime('%Y%m%d')}.{self.format}"
            else:  # monthly
                filename = f"monthly_{self.start_date.strftime('%Y%m')}.{self.format}"
                
            file_path = os.path.join(self.output_dir, filename)
            
            # 根据格式生成报告
            if self.format == 'pdf':
                self.report_generator.generate_pdf_report(report_data, file_path)
            elif self.format == 'html':
                self.report_generator.generate_html_report(report_data, file_path)
            elif self.format == 'csv':
                self.report_generator.generate_csv_report(report_data, file_path)
            else:
                raise ValueError(f"不支持的报告格式: {self.format}")
            
            # 4. 完成
            self.progress_updated.emit(self.report_type, 100)
            self.task_completed.emit(
                True, file_path, f"{type_desc}报告生成成功"
            )
            
        except Exception as e:
            error_msg = f"{type_desc}报告生成失败: {str(e)}"
            self.progress_updated.emit(self.report_type, 0)
            self.task_completed.emit(False, "", error_msg)
