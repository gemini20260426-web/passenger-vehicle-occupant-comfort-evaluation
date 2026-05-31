"""系统集成与API接口模块（提供外部系统访问和数据交互能力）"""
import logging
import os
import json
import csv
import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
from flask import Flask, request, jsonify, send_file, Blueprint
from flask_cors import CORS
import pandas as pd
from PySide6.QtCore import QObject, Signal, Slot, QThread, QMutex, QMutexLocker
from io import BytesIO, StringIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

class SystemIntegration(QObject):
    """系统集成与API接口模块（保持原有类名）"""
    # 信号定义（新增状态通知机制）
    api_request_received = Signal(str, str)  # 请求路径, 请求方法
    api_response_sent = Signal(str, int)  # 请求路径, 响应状态码
    export_progress_updated = Signal(int, str)  # 进度(0-100), 状态信息
    export_completed = Signal(str, str)  # 导出文件路径, 格式
    error_occurred = Signal(str)  # 错误信息

    def __init__(self, core_services, port: int = 5000):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.core_services = core_services  # 核心服务引用（包含所有业务模块）
        self.port = port
        
        # 线程安全锁（新增）
        self.api_lock = QMutex()
        
        # API服务器状态（新增）
        self.server_running = False
        self.export_in_progress = False
        
        # 初始化API蓝图（保持原有方法）
        self.api = Blueprint('driving_behavior_api', __name__)
        self._register_routes()
        
        # 初始化Flask应用（保持原有方法）
        self.app = Flask(__name__)
        CORS(self.app)  # 允许跨域请求
        self.app.register_blueprint(self.api, url_prefix='/api/v1')
        
        # 初始化Webhook列表（新增）
        self.webhooks = {
            'risk_alert': []  # 风险预警Webhook
        }

    def _register_routes(self) -> None:
        """注册API路由（保持原有方法）"""
        # 司机管理接口
        self.api.add_url_rule('/drivers', 'get_drivers', self.get_drivers, methods=['GET'])
        self.api.add_url_rule('/drivers/<driver_id>', 'get_driver', self.get_driver, methods=['GET'])
        self.api.add_url_rule('/drivers', 'create_driver', self.create_driver, methods=['POST'])
        self.api.add_url_rule('/drivers/<driver_id>', 'update_driver', self.update_driver, methods=['PUT'])
        self.api.add_url_rule('/drivers/<driver_id>', 'delete_driver', self.delete_driver, methods=['DELETE'])
        
        # 行为分析接口
        self.api.add_url_rule('/drivers/<driver_id>/behavior', 'get_driver_behavior', self.get_driver_behavior, methods=['GET'])
        self.api.add_url_rule('/drivers/<driver_id>/risk', 'get_driver_risk', self.get_driver_risk, methods=['GET'])
        self.api.add_url_rule('/drivers/<driver_id>/predictions', 'get_driver_predictions', self.get_driver_predictions, methods=['GET'])
        
        # 统计分析接口
        self.api.add_url_rule('/statistics/overall', 'get_overall_statistics', self.get_overall_statistics, methods=['GET'])
        self.api.add_url_rule('/statistics/risk-distribution', 'get_risk_distribution', self.get_risk_distribution, methods=['GET'])
        self.api.add_url_rule('/statistics/daily-trends', 'get_daily_trends', self.get_daily_trends, methods=['GET'])
        
        # 数据导出接口
        self.api.add_url_rule('/export/drivers', 'export_drivers', self.export_drivers, methods=['GET'])
        self.api.add_url_rule('/export/behavior/<driver_id>', 'export_behavior', self.export_behavior, methods=['GET'])
        self.api.add_url_rule('/export/risk-report/<driver_id>', 'export_risk_report', self.export_risk_report, methods=['GET'])
        
        # Webhook管理接口
        self.api.add_url_rule('/webhooks', 'get_webhooks', self.get_webhooks, methods=['GET'])
        self.api.add_url_rule('/webhooks', 'add_webhook', self.add_webhook, methods=['POST'])
        self.api.add_url_rule('/webhooks/<webhook_id>', 'remove_webhook', self.remove_webhook, methods=['DELETE'])
        
        # 系统状态接口
        self.api.add_url_rule('/status', 'get_system_status', self.get_system_status, methods=['GET'])

    def start_server(self) -> None:
        """启动API服务器（保持原有方法）"""
        with QMutexLocker(self.api_lock):
            if self.server_running:
                self.logger.warning("API服务器已在运行中")
                return
                
            # 在新线程中启动服务器
            self.server_thread = ServerThread(self.app, self.port)
            self.server_thread.started.connect(self._on_server_started)
            self.server_thread.finished.connect(self._on_server_stopped)
            self.server_thread.start()

    def stop_server(self) -> None:
        """停止API服务器（新增）"""
        with QMutexLocker(self.api_lock):
            if not self.server_running:
                self.logger.warning("API服务器未在运行中")
                return
                
            # 停止服务器线程
            self.server_thread.stop()

    def add_webhook(self, event_type: str, url: str, secret: Optional[str] = None) -> str:
        """添加Webhook（新增）"""
        if event_type not in self.webhooks:
            raise ValueError(f"不支持的事件类型: {event_type}")
            
        # 生成唯一ID
        webhook_id = f"{event_type}_{datetime.datetime.now().timestamp()}"
        
        # 添加到Webhook列表
        self.webhooks[event_type].append({
            'id': webhook_id,
            'url': url,
            'secret': secret,
            'created_at': datetime.datetime.now().timestamp()
        })
        
        self.logger.info(f"已添加Webhook: {event_type} -> {url}")
        return webhook_id

    def remove_webhook(self, webhook_id: str) -> bool:
        """移除Webhook（新增）"""
        for event_type in self.webhooks:
            for i, webhook in enumerate(self.webhooks[event_type]):
                if webhook['id'] == webhook_id:
                    del self.webhooks[event_type][i]
                    self.logger.info(f"已移除Webhook: {webhook_id}")
                    return True
                    
        return False

    def trigger_webhooks(self, event_type: str, data: Dict[str, Any]) -> None:
        """触发Webhook（新增）"""
        if event_type not in self.webhooks:
            return
            
        # 在新线程中处理Webhook调用，避免阻塞主线程
        for webhook in self.webhooks[event_type]:
            webhook_thread = WebhookThread(
                event_type=event_type,
                webhook=webhook,
                data=data
            )
            webhook_thread.start()

    def export_data(self, export_type: str, driver_id: Optional[str] = None, 
                   format: str = 'csv', start_time: Optional[float] = None,
                   end_time: Optional[float] = None) -> Tuple[str, BytesIO]:
        """导出数据（保持原有方法）"""
        try:
            with QMutexLocker(self.api_lock):
                if self.export_in_progress:
                    raise Exception("有导出任务正在进行中，请稍后再试")
                    
                self.export_in_progress = True
                self.export_progress_updated.emit(0, "开始准备导出数据...")
            
            # 根据导出类型处理
            if export_type == 'drivers':
                # 导出司机列表
                data = self.core_services.driver_manager.get_all_drivers()
                filename, buffer = self._export_drivers(data, format)
                
            elif export_type == 'behavior' and driver_id:
                # 导出驾驶行为数据
                if not start_time:
                    start_time = (datetime.datetime.now() - datetime.timedelta(days=7)).timestamp()
                if not end_time:
                    end_time = datetime.datetime.now().timestamp()
                    
                data = self.core_services.storage_manager.get_driver_behavior_data(
                    driver_id=driver_id,
                    start_time=start_time,
                    end_time=end_time
                )
                filename, buffer = self._export_behavior(driver_id, data, format, start_time, end_time)
                
            elif export_type == 'risk_report' and driver_id:
                # 导出风险报告
                risk_score = self.core_services.prediction_engine.get_driver_risk_score(driver_id)
                predictions = self.core_services.prediction_engine.predict_behavior(driver_id, hours=24)
                
                if not risk_score or not predictions:
                    raise Exception("无法获取足够的风险评估数据")
                    
                filename, buffer = self._export_risk_report(driver_id, risk_score, predictions, format)
                
            else:
                raise Exception(f"不支持的导出类型: {export_type}")
                
            self.export_progress_updated.emit(100, "数据导出完成")
            return filename, buffer
            
        except Exception as e:
            error_msg = f"数据导出失败: {str(e)}"
            self.logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            raise
        finally:
            with QMutexLocker(self.api_lock):
                self.export_in_progress = False

    def _export_drivers(self, drivers: List[Dict[str, Any]], format: str) -> Tuple[str, BytesIO]:
        """导出司机列表（新增）"""
        self.export_progress_updated.emit(20, "正在处理司机数据...")
        
        # 准备数据
        df = pd.DataFrame(drivers)
        
        # 选择需要导出的字段
        if not df.empty:
            columns = ['id', 'name', 'vehicle', 'experience', 'status', 'created_at']
            df = df.reindex(columns=columns)
            
            # 格式化时间字段
            if 'created_at' in df.columns:
                df['created_at'] = df['created_at'].apply(
                    lambda x: datetime.datetime.fromtimestamp(x).strftime("%Y-%m-%d %H:%M") 
                    if x else ""
                )
        
        self.export_progress_updated.emit(50, "正在生成导出文件...")
        
        # 根据格式导出
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"司机列表_{timestamp}"
        
        if format == 'csv':
            buffer = BytesIO()
            df.to_csv(buffer, index=False, encoding='utf-8-sig')
            buffer.seek(0)
            filename += ".csv"
            
        elif format == 'excel':
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='司机列表')
            buffer.seek(0)
            filename += ".xlsx"
            
        elif format == 'pdf':
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            
            # 添加标题
            elements = []
            elements.append(Paragraph("司机列表", styles['Title']))
            elements.append(Spacer(1, 12))
            
            # 添加表格
            if not df.empty:
                # 准备表格数据
                table_data = [df.columns.tolist()]
                table_data.extend(df.values.tolist())
                
                # 创建表格
                table = Table(table_data)
                
                # 设置表格样式
                style = TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.grey),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0,0), (-1,0), 12),
                    ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                    ('GRID', (0,0), (-1,-1), 1, colors.black)
                ])
                table.setStyle(style)
                elements.append(table)
            else:
                elements.append(Paragraph("没有司机数据可导出", styles['Normal']))
                
            # 构建PDF
            doc.build(elements)
            buffer.seek(0)
            filename += ".pdf"
            
        else:
            raise Exception(f"不支持的导出格式: {format}")
            
        self.export_progress_updated.emit(80, "文件生成完成...")
        return filename, buffer

    def _export_behavior(self, driver_id: str, behavior_data: List[Dict[str, Any]], 
                        format: str, start_time: float, end_time: float) -> Tuple[str, BytesIO]:
        """导出驾驶行为数据（新增）"""
        self.export_progress_updated.emit(20, "正在处理驾驶行为数据...")
        
        # 获取司机信息
        driver_info = self.core_services.driver_manager.get_driver_info(driver_id)
        driver_name = driver_info.get('name', driver_id) if driver_info else driver_id
        
        # 准备数据
        df = pd.DataFrame(behavior_data)
        
        # 选择需要导出的字段
        if not df.empty:
            columns = ['timestamp', 'location', 'speed', 'acceleration', 
                      'direction', 'lane_position', 'speed_limit']
            df = df.reindex(columns=columns)
            
            # 格式化时间字段
            if 'timestamp' in df.columns:
                df['timestamp'] = df['timestamp'].apply(
                    lambda x: datetime.datetime.fromtimestamp(x).strftime("%Y-%m-%d %H:%M:%S") 
                    if x else ""
                )
        
        self.export_progress_updated.emit(50, "正在生成导出文件...")
        
        # 根据格式导出
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        start_str = datetime.datetime.fromtimestamp(start_time).strftime("%Y%m%d")
        end_str = datetime.datetime.fromtimestamp(end_time).strftime("%Y%m%d")
        filename = f"{driver_name}_驾驶行为_{start_str}-{end_str}_{timestamp}"
        
        if format == 'csv':
            buffer = BytesIO()
            df.to_csv(buffer, index=False, encoding='utf-8-sig')
            buffer.seek(0)
            filename += ".csv"
            
        elif format == 'excel':
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='驾驶行为数据')
            buffer.seek(0)
            filename += ".xlsx"
            
        elif format == 'pdf':
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            
            # 添加标题和信息
            elements = []
            elements.append(Paragraph(f"{driver_name} 驾驶行为数据", styles['Title']))
            elements.append(Paragraph(f"时间段: {start_str} 至 {end_str}", styles['Normal']))
            elements.append(Spacer(1, 12))
            
            # 添加表格
            if not df.empty:
                # 准备表格数据（限制最多1000行）
                max_rows = 1000
                table_data = [df.columns.tolist()]
                
                if len(df) > max_rows:
                    elements.append(Paragraph(f"注: 数据量过大，仅显示前{max_rows}条记录", styles['Italic']))
                    elements.append(Spacer(1, 12))
                    table_data.extend(df.head(max_rows).values.tolist())
                else:
                    table_data.extend(df.values.tolist())
                
                # 创建表格
                table = Table(table_data)
                
                # 设置表格样式
                style = TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.grey),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0,0), (-1,0), 12),
                    ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                    ('GRID', (0,0), (-1,-1), 1, colors.black)
                ])
                table.setStyle(style)
                elements.append(table)
            else:
                elements.append(Paragraph("没有驾驶行为数据可导出", styles['Normal']))
                
            # 构建PDF
            doc.build(elements)
            buffer.seek(0)
            filename += ".pdf"
            
        else:
            raise Exception(f"不支持的导出格式: {format}")
            
        self.export_progress_updated.emit(80, "文件生成完成...")
        return filename, buffer

    def _export_risk_report(self, driver_id: str, risk_score: Dict[str, Any], 
                          predictions: List[Dict[str, Any]], format: str) -> Tuple[str, BytesIO]:
        """导出风险报告（新增）"""
        self.export_progress_updated.emit(20, "正在处理风险报告数据...")
        
        # 获取司机信息
        driver_info = self.core_services.driver_manager.get_driver_info(driver_id)
        driver_name = driver_info.get('name', driver_id) if driver_info else driver_id
        
        self.export_progress_updated.emit(40, "正在生成风险报告内容...")
        
        # 根据格式导出
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{driver_name}_驾驶风险报告_{timestamp}"
        
        if format == 'pdf':
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            
            # 添加标题和信息
            elements = []
            elements.append(Paragraph(f"{driver_name} 驾驶风险报告", styles['Title']))
            elements.append(Paragraph(f"评估时间: {risk_score['evaluation_time_str']}", styles['Normal']))
            elements.append(Paragraph(f"评估周期: {risk_score['evaluation_period']}", styles['Normal']))
            elements.append(Spacer(1, 12))
            
            # 整体风险评分
            elements.append(Paragraph("一、整体风险评估", styles['Heading2']))
            
            risk_table_data = [
                ["风险评分", f"{risk_score['overall_risk']} / 100"],
                ["风险等级", risk_score['risk_level']],
                ["高风险行为数量", f"{risk_score['risky_behavior_count']} 条"],
                ["高风险行为占比", f"{risk_score['risky_behavior_ratio']}%"],
                ["总记录数", f"{risk_score['total_records']} 条"]
            ]
            
            risk_table = Table(risk_table_data, colWidths=[200, 200])
            risk_table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('BACKGROUND', (0,0), (0,-1), colors.lightblue),
                ('ALIGN', (0,0), (0,-1), 'RIGHT'),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ]))
            elements.append(risk_table)
            elements.append(Spacer(1, 12))
            
            # 主要风险因素
            elements.append(Paragraph("二、主要风险因素", styles['Heading2']))
            
            if risk_score.get('risk_factors'):
                factors_table_data = [["风险因素", "风险发生率", "风险贡献度"]]
                for factor in risk_score['risk_factors']:
                    factors_table_data.append([
                        factor['description'],
                        f"{factor['risk_ratio']}%",
                        f"{factor['contribution']}%"
                    ])
                
                factors_table = Table(factors_table_data)
                factors_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.grey),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('GRID', (0,0), (-1,-1), 1, colors.black)
                ]))
                elements.append(factors_table)
            else:
                elements.append(Paragraph("没有足够的风险因素数据", styles['Normal']))
                
            elements.append(Spacer(1, 12))
            
            # 时段风险分布
            elements.append(Paragraph("三、时段风险分布", styles['Heading2']))
            
            if risk_score.get('hourly_risk'):
                hourly_table_data = [["时段", "平均风险", "高风险占比"]]
                for hour_data in risk_score['hourly_risk']:
                    hourly_table_data.append([
                        hour_data['hour_str'],
                        f"{hour_data['avg_risk']}%",
                        f"{hour_data['risky_ratio']}%"
                    ])
                
                hourly_table = Table(hourly_table_data)
                hourly_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.grey),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('GRID', (0,0), (-1,-1), 1, colors.black)
                ]))
                elements.append(hourly_table)
            else:
                elements.append(Paragraph("没有足够的时段风险数据", styles['Normal']))
                
            elements.append(Spacer(1, 12))
            
            # 高风险行为记录
            elements.append(Paragraph("四、近期高风险行为记录", styles['Heading2']))
            
            # 筛选高风险记录
            high_risk_predictions = [p for p in predictions if p['risk_level'] == '高'][:10]  # 最多显示10条
            
            if high_risk_predictions:
                risky_table_data = [["时间", "位置", "速度", "加速度", "风险概率"]]
                for pred in high_risk_predictions:
                    risky_table_data.append([
                        pred['timestamp_str'],
                        pred['location'],
                        f"{pred['speed']} km/h",
                        f"{pred['acceleration']} m/s²",
                        f"{pred['risk_probability']:.2%}"
                    ])
                
                risky_table = Table(risky_table_data)
                risky_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.grey),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('GRID', (0,0), (-1,-1), 1, colors.black)
                ]))
                elements.append(risky_table)
            else:
                elements.append(Paragraph("没有高风险行为记录", styles['Normal']))
                
            # 构建PDF
            doc.build(elements)
            buffer.seek(0)
            filename += ".pdf"
            
        elif format == 'excel':
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                # 整体风险评分
                risk_df = pd.DataFrame({
                    '指标': ['风险评分', '风险等级', '高风险行为数量', '高风险行为占比', '总记录数'],
                    '值': [
                        f"{risk_score['overall_risk']} / 100",
                        risk_score['risk_level'],
                        f"{risk_score['risky_behavior_count']} 条",
                        f"{risk_score['risky_behavior_ratio']}%",
                        f"{risk_score['total_records']} 条"
                    ]
                })
                risk_df.to_excel(writer, index=False, sheet_name='整体风险评估')
                
                # 主要风险因素
                if risk_score.get('risk_factors'):
                    factors_df = pd.DataFrame(risk_score['risk_factors'])
                    factors_df.to_excel(writer, index=False, sheet_name='风险因素分析')
                
                # 时段风险分布
                if risk_score.get('hourly_risk'):
                    hourly_df = pd.DataFrame(risk_score['hourly_risk'])
                    hourly_df.to_excel(writer, index=False, sheet_name='时段风险分布')
                
                # 高风险行为记录
                high_risk_predictions = [p for p in predictions if p['risk_level'] == '高']
                if high_risk_predictions:
                    risky_df = pd.DataFrame(high_risk_predictions)
                    risky_df.to_excel(writer, index=False, sheet_name='高风险行为记录')
            
            buffer.seek(0)
            filename += ".xlsx"
            
        else:
            raise Exception(f"不支持的导出格式: {format}")
            
        self.export_progress_updated.emit(80, "报告生成完成...")
        return filename, buffer

    @Slot()
    def _on_server_started(self) -> None:
        """处理服务器启动（新增）"""
        with QMutexLocker(self.api_lock):
            self.server_running = True
        self.logger.info(f"API服务器已启动，监听端口: {self.port}")

    @Slot()
    def _on_server_stopped(self) -> None:
        """处理服务器停止（新增）"""
        with QMutexLocker(self.api_lock):
            self.server_running = False
        self.logger.info("API服务器已停止")

    # API接口实现
    def get_drivers(self) -> jsonify:
        """获取司机列表API（新增）"""
        self.api_request_received.emit('/drivers', 'GET')
        
        try:
            # 获取查询参数
            page = request.args.get('page', 1, type=int)
            limit = request.args.get('limit', 20, type=int)
            status = request.args.get('status')
            
            # 获取司机列表
            drivers = self.core_services.driver_manager.get_all_drivers()
            
            # 筛选状态
            if status:
                drivers = [d for d in drivers if d.get('status') == status]
                
            # 分页
            total = len(drivers)
            start = (page - 1) * limit
            end = start + limit
            paginated = drivers[start:end]
            
            response = {
                'success': True,
                'data': paginated,
                'pagination': {
                    'total': total,
                    'page': page,
                    'limit': limit,
                    'pages': (total + limit - 1) // limit
                }
            }
            
            self.api_response_sent.emit('/drivers', 200)
            return jsonify(response)
            
        except Exception as e:
            error_msg = f"获取司机列表失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit('/drivers', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def get_driver(self, driver_id: str) -> jsonify:
        """获取司机详情API（新增）"""
        self.api_request_received.emit(f'/drivers/{driver_id}', 'GET')
        
        try:
            # 获取司机信息
            driver = self.core_services.driver_manager.get_driver_info(driver_id)
            
            if not driver:
                self.api_response_sent.emit(f'/drivers/{driver_id}', 404)
                return jsonify({
                    'success': False,
                    'error': f"司机 {driver_id} 不存在"
                }), 404
                
            response = {
                'success': True,
                'data': driver
            }
            
            self.api_response_sent.emit(f'/drivers/{driver_id}', 200)
            return jsonify(response)
            
        except Exception as e:
            error_msg = f"获取司机详情失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit(f'/drivers/{driver_id}', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def create_driver(self) -> jsonify:
        """创建司机API（新增）"""
        self.api_request_received.emit('/drivers', 'POST')
        
        try:
            # 获取请求数据
            data = request.get_json()
            
            if not data or not data.get('id') or not data.get('name'):
                self.api_response_sent.emit('/drivers', 400)
                return jsonify({
                    'success': False,
                    'error': "司机ID和姓名为必填项"
                }), 400
                
            # 创建司机
            result = self.core_services.driver_manager.create_driver(
                driver_id=data['id'],
                name=data['name'],
                vehicle=data.get('vehicle', ''),
                experience=data.get('experience', 0),
                status=data.get('status', 'active')
            )
            
            if result:
                self.api_response_sent.emit('/drivers', 201)
                return jsonify({
                    'success': True,
                    'message': f"司机 {data['id']} 创建成功",
                    'data': {
                        'id': data['id'],
                        'name': data['name']
                    }
                }), 201
            else:
                self.api_response_sent.emit('/drivers', 400)
                return jsonify({
                    'success': False,
                    'error': f"司机 {data['id']} 已存在"
                }), 400
                
        except Exception as e:
            error_msg = f"创建司机失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit('/drivers', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def update_driver(self, driver_id: str) -> jsonify:
        """更新司机API（新增）"""
        self.api_request_received.emit(f'/drivers/{driver_id}', 'PUT')
        
        try:
            # 获取请求数据
            data = request.get_json()
            
            if not data:
                self.api_response_sent.emit(f'/drivers/{driver_id}', 400)
                return jsonify({
                    'success': False,
                    'error': "更新数据不能为空"
                }), 400
                
            # 更新司机
            result = self.core_services.driver_manager.update_driver(
                driver_id=driver_id,
                **data
            )
            
            if result:
                self.api_response_sent.emit(f'/drivers/{driver_id}', 200)
                return jsonify({
                    'success': True,
                    'message': f"司机 {driver_id} 更新成功"
                })
            else:
                self.api_response_sent.emit(f'/drivers/{driver_id}', 404)
                return jsonify({
                    'success': False,
                    'error': f"司机 {driver_id} 不存在"
                }), 404
                
        except Exception as e:
            error_msg = f"更新司机失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit(f'/drivers/{driver_id}', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def delete_driver(self, driver_id: str) -> jsonify:
        """删除司机API（新增）"""
        self.api_request_received.emit(f'/drivers/{driver_id}', 'DELETE')
        
        try:
            # 删除司机
            result = self.core_services.driver_manager.delete_driver(driver_id)
            
            if result:
                self.api_response_sent.emit(f'/drivers/{driver_id}', 200)
                return jsonify({
                    'success': True,
                    'message': f"司机 {driver_id} 删除成功"
                })
            else:
                self.api_response_sent.emit(f'/drivers/{driver_id}', 404)
                return jsonify({
                    'success': False,
                    'error': f"司机 {driver_id} 不存在"
                }), 404
                
        except Exception as e:
            error_msg = f"删除司机失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit(f'/drivers/{driver_id}', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def get_driver_behavior(self, driver_id: str) -> jsonify:
        """获取司机驾驶行为数据API（新增）"""
        self.api_request_received.emit(f'/drivers/{driver_id}/behavior', 'GET')
        
        try:
            # 获取查询参数
            start_time = request.args.get('start_time', type=float)
            end_time = request.args.get('end_time', type=float)
            limit = request.args.get('limit', 100, type=int)
            
            # 设置默认时间范围（最近7天）
            if not end_time:
                end_time = datetime.datetime.now().timestamp()
            if not start_time:
                start_time = end_time - (7 * 86400)
                
            # 获取驾驶行为数据
            behavior_data = self.core_services.storage_manager.get_driver_behavior_data(
                driver_id=driver_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )
            
            response = {
                'success': True,
                'data': behavior_data,
                'parameters': {
                    'driver_id': driver_id,
                    'start_time': start_time,
                    'end_time': end_time,
                    'count': len(behavior_data)
                }
            }
            
            self.api_response_sent.emit(f'/drivers/{driver_id}/behavior', 200)
            return jsonify(response)
            
        except Exception as e:
            error_msg = f"获取驾驶行为数据失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit(f'/drivers/{driver_id}/behavior', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def get_driver_risk(self, driver_id: str) -> jsonify:
        """获取司机风险评分API（新增）"""
        self.api_request_received.emit(f'/drivers/{driver_id}/risk', 'GET')
        
        try:
            # 获取查询参数
            days = request.args.get('days', 7, type=int)
            
            # 获取风险评分
            risk_score = self.core_services.prediction_engine.get_driver_risk_score(
                driver_id=driver_id,
                days=days
            )
            
            if not risk_score:
                self.api_response_sent.emit(f'/drivers/{driver_id}/risk', 404)
                return jsonify({
                    'success': False,
                    'error': f"无法获取司机 {driver_id} 的风险评分，可能数据不足"
                }), 404
                
            response = {
                'success': True,
                'data': risk_score,
                'parameters': {
                    'driver_id': driver_id,
                    'evaluation_period': f"最近{days}天"
                }
            }
            
            self.api_response_sent.emit(f'/drivers/{driver_id}/risk', 200)
            return jsonify(response)
            
        except Exception as e:
            error_msg = f"获取司机风险评分失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit(f'/drivers/{driver_id}/risk', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def get_driver_predictions(self, driver_id: str) -> jsonify:
        """获取司机风险预测API（新增）"""
        self.api_request_received.emit(f'/drivers/{driver_id}/predictions', 'GET')
        
        try:
            # 获取查询参数
            hours = request.args.get('hours', 24, type=int)
            
            # 获取预测结果
            predictions = self.core_services.prediction_engine.predict_behavior(
                driver_id=driver_id,
                hours=hours
            )
            
            if not predictions:
                self.api_response_sent.emit(f'/drivers/{driver_id}/predictions', 404)
                return jsonify({
                    'success': False,
                    'error': f"无法获取司机 {driver_id} 的风险预测，可能数据不足"
                }), 404
                
            response = {
                'success': True,
                'data': predictions,
                'parameters': {
                    'driver_id': driver_id,
                    'time_range': f"最近{hours}小时",
                    'count': len(predictions),
                    'risky_count': sum(1 for p in predictions if p['is_risky'])
                }
            }
            
            self.api_response_sent.emit(f'/drivers/{driver_id}/predictions', 200)
            return jsonify(response)
            
        except Exception as e:
            error_msg = f"获取司机风险预测失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit(f'/drivers/{driver_id}/predictions', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def get_overall_statistics(self) -> jsonify:
        """获取整体统计数据API（新增）"""
        self.api_request_received.emit('/statistics/overall', 'GET')
        
        try:
            # 获取统计数据
            stats = self.core_services.analysis_service.get_overall_statistics()
            
            response = {
                'success': True,
                'data': stats
            }
            
            self.api_response_sent.emit('/statistics/overall', 200)
            return jsonify(response)
            
        except Exception as e:
            error_msg = f"获取整体统计数据失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit('/statistics/overall', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def get_risk_distribution(self) -> jsonify:
        """获取风险分布统计API（新增）"""
        self.api_request_received.emit('/statistics/risk-distribution', 'GET')
        
        try:
            # 获取风险分布
            distribution = self.core_services.analysis_service.get_risk_distribution()
            
            response = {
                'success': True,
                'data': distribution
            }
            
            self.api_response_sent.emit('/statistics/risk-distribution', 200)
            return jsonify(response)
            
        except Exception as e:
            error_msg = f"获取风险分布统计失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit('/statistics/risk-distribution', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def get_daily_trends(self) -> jsonify:
        """获取每日趋势统计API（新增）"""
        self.api_request_received.emit('/statistics/daily-trends', 'GET')
        
        try:
            # 获取查询参数
            days = request.args.get('days', 30, type=int)
            
            # 获取每日趋势
            trends = self.core_services.analysis_service.get_daily_trends(days=days)
            
            response = {
                'success': True,
                'data': trends,
                'parameters': {
                    'days': days
                }
            }
            
            self.api_response_sent.emit('/statistics/daily-trends', 200)
            return jsonify(response)
            
        except Exception as e:
            error_msg = f"获取每日趋势统计失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit('/statistics/daily-trends', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def export_drivers(self) -> send_file:
        """导出司机列表API（新增）"""
        self.api_request_received.emit('/export/drivers', 'GET')
        
        try:
            # 获取查询参数
            format = request.args.get('format', 'csv').lower()
            if format not in ['csv', 'excel', 'pdf']:
                format = 'csv'
                
            # 导出数据
            filename, buffer = self.export_data(
                export_type='drivers',
                format=format
            )
            
            self.export_completed.emit(filename, format)
            self.api_response_sent.emit('/export/drivers', 200)
            return send_file(
                buffer,
                mimetype=self._get_mimetype(format),
                download_name=filename,
                as_attachment=True
            )
            
        except Exception as e:
            error_msg = f"导出司机列表失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit('/export/drivers', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def export_behavior(self, driver_id: str) -> send_file:
        """导出驾驶行为数据API（新增）"""
        self.api_request_received.emit(f'/export/behavior/{driver_id}', 'GET')
        
        try:
            # 获取查询参数
            format = request.args.get('format', 'csv').lower()
            if format not in ['csv', 'excel', 'pdf']:
                format = 'csv'
                
            start_time = request.args.get('start_time', type=float)
            end_time = request.args.get('end_time', type=float)
            
            # 导出数据
            filename, buffer = self.export_data(
                export_type='behavior',
                driver_id=driver_id,
                format=format,
                start_time=start_time,
                end_time=end_time
            )
            
            self.export_completed.emit(filename, format)
            self.api_response_sent.emit(f'/export/behavior/{driver_id}', 200)
            return send_file(
                buffer,
                mimetype=self._get_mimetype(format),
                download_name=filename,
                as_attachment=True
            )
            
        except Exception as e:
            error_msg = f"导出驾驶行为数据失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit(f'/export/behavior/{driver_id}', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def export_risk_report(self, driver_id: str) -> send_file:
        """导出风险报告API（新增）"""
        self.api_request_received.emit(f'/export/risk-report/{driver_id}', 'GET')
        
        try:
            # 获取查询参数
            format = request.args.get('format', 'pdf').lower()
            if format not in ['excel', 'pdf']:
                format = 'pdf'
                
            # 导出数据
            filename, buffer = self.export_data(
                export_type='risk_report',
                driver_id=driver_id,
                format=format
            )
            
            self.export_completed.emit(filename, format)
            self.api_response_sent.emit(f'/export/risk-report/{driver_id}', 200)
            return send_file(
                buffer,
                mimetype=self._get_mimetype(format),
                download_name=filename,
                as_attachment=True
            )
            
        except Exception as e:
            error_msg = f"导出风险报告失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit(f'/export/risk-report/{driver_id}', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def get_webhooks(self) -> jsonify:
        """获取Webhook列表API（新增）"""
        self.api_request_received.emit('/webhooks', 'GET')
        
        try:
            # 整理Webhook数据
            webhooks = []
            for event_type, items in self.webhooks.items():
                for item in items:
                    webhooks.append({
                        'id': item['id'],
                        'event_type': event_type,
                        'url': item['url'],
                        'created_at': item['created_at'],
                        'created_at_str': datetime.datetime.fromtimestamp(item['created_at']).strftime("%Y-%m-%d %H:%M:%S")
                    })
            
            response = {
                'success': True,
                'data': webhooks,
                'count': len(webhooks)
            }
            
            self.api_response_sent.emit('/webhooks', 200)
            return jsonify(response)
            
        except Exception as e:
            error_msg = f"获取Webhook列表失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit('/webhooks', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def add_webhook(self) -> jsonify:
        """添加Webhook API（新增）"""
        self.api_request_received.emit('/webhooks', 'POST')
        
        try:
            # 获取请求数据
            data = request.get_json()
            
            if not data or not data.get('event_type') or not data.get('url'):
                self.api_response_sent.emit('/webhooks', 400)
                return jsonify({
                    'success': False,
                    'error': "事件类型和URL为必填项"
                }), 400
                
            # 添加Webhook
            webhook_id = self.add_webhook(
                event_type=data['event_type'],
                url=data['url'],
                secret=data.get('secret')
            )
            
            self.api_response_sent.emit('/webhooks', 201)
            return jsonify({
                'success': True,
                'message': "Webhook添加成功",
                'data': {
                    'id': webhook_id,
                    'event_type': data['event_type'],
                    'url': data['url']
                }
            }), 201
                
        except ValueError as e:
            self.api_response_sent.emit('/webhooks', 400)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
            
        except Exception as e:
            error_msg = f"添加Webhook失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit('/webhooks', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def remove_webhook(self, webhook_id: str) -> jsonify:
        """删除Webhook API（新增）"""
        self.api_request_received.emit(f'/webhooks/{webhook_id}', 'DELETE')
        
        try:
            # 删除Webhook
            result = self.remove_webhook(webhook_id)
            
            if result:
                self.api_response_sent.emit(f'/webhooks/{webhook_id}', 200)
                return jsonify({
                    'success': True,
                    'message': f"Webhook {webhook_id} 删除成功"
                })
            else:
                self.api_response_sent.emit(f'/webhooks/{webhook_id}', 404)
                return jsonify({
                    'success': False,
                    'error': f"Webhook {webhook_id} 不存在"
                }), 404
                
        except Exception as e:
            error_msg = f"删除Webhook失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit(f'/webhooks/{webhook_id}', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def get_system_status(self) -> jsonify:
        """获取系统状态API（新增）"""
        self.api_request_received.emit('/status', 'GET')
        
        try:
            # 获取各模块状态
            status = {
                'server_running': self.server_running,
                'database_connected': self.core_services.storage_manager.is_connected(),
                'prediction_model_loaded': self.core_services.prediction_engine.get_model_status()['loaded'],
                'driver_count': len(self.core_services.driver_manager.get_all_drivers()),
                'record_count': self.core_services.storage_manager.get_record_count(),
                'last_data_update': self.core_services.storage_manager.get_last_update_time(),
                'system_time': datetime.datetime.now().timestamp(),
                'system_time_str': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            response = {
                'success': True,
                'data': status
            }
            
            self.api_response_sent.emit('/status', 200)
            return jsonify(response)
            
        except Exception as e:
            error_msg = f"获取系统状态失败: {str(e)}"
            self.logger.error(error_msg)
            self.api_response_sent.emit('/status', 500)
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    def _get_mimetype(self, format: str) -> str:
        """获取文件MIME类型（新增）"""
        mimetypes = {
            'csv': 'text/csv',
            'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'pdf': 'application/pdf'
        }
        return mimetypes.get(format, 'application/octet-stream')


class ServerThread(QThread):
    """API服务器线程（新增）"""
    def __init__(self, app, port: int):
        super().__init__()
        self.app = app
        self.port = port
        self.running = False
        
    def run(self) -> None:
        """运行服务器"""
        self.running = True
        try:
            # 使用不阻塞的方式运行Flask服务器
            self.app.run(
                host='0.0.0.0',
                port=self.port,
                debug=False,
                use_reloader=False  # 禁用自动重载，避免创建新进程
            )
        except Exception as e:
            logging.error(f"API服务器运行错误: {str(e)}")
            
    def stop(self) -> None:
        """停止服务器"""
        self.running = False
        # Flask服务器没有直接的停止方法，这里通过终止线程实现
        self.terminate()


class WebhookThread(QThread):
    """Webhook调用线程（新增）"""
    def __init__(self, event_type: str, webhook: Dict[str, Any], data: Dict[str, Any]):
        super().__init__()
        self.event_type = event_type
        self.webhook = webhook
        self.data = data
        self.logger = logging.getLogger(__name__)
        
    def run(self) -> None:
        """执行Webhook调用"""
        try:
            import requests
            import hmac
            import hashlib
            
            # 准备请求数据
            payload = {
                'event_type': self.event_type,
                'timestamp': datetime.datetime.now().timestamp(),
                'data': self.data
            }
            
            # 构建请求头
            headers = {
                'Content-Type': 'application/json',
                'X-Event-Type': self.event_type
            }
            
            # 如果设置了密钥，添加签名
            if self.webhook.get('secret'):
                json_payload = json.dumps(payload, sort_keys=True)
                signature = hmac.new(
                    self.webhook['secret'].encode('utf-8'),
                    json_payload.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                headers['X-Signature'] = signature
            
            # 发送请求
            response = requests.post(
                self.webhook['url'],
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info(f"Webhook调用成功: {self.event_type} -> {self.webhook['url']}")
            else:
                self.logger.warning(
                    f"Webhook调用返回非成功状态: {response.status_code} "
                    f"for {self.event_type} -> {self.webhook['url']}"
                )
                
        except Exception as e:
            self.logger.error(
                f"Webhook调用失败: {str(e)} "
                f"for {self.event_type} -> {self.webhook['url']}"
            )
