import logging
from .data_reader import FileDataReader
from communication.mqtt_client import MQTTClient
from .data_parser import IMUDataParser
from ..analysis.base_analyzer import BasicDrivingAnalyzer
from ..storage.data_storage import DataStorage
from .buffer_manager import BufferManager
from .proto_serial_reader import ProtoSerialDataReader

# 创建简单的配置类来替代缺失的配置管理器
class RedisConfig:
    def __init__(self, **kwargs):
        self.host = kwargs.get('host', 'localhost')
        self.port = kwargs.get('port', 6379)
        self.db = kwargs.get('db', 0)

class MySQLConfig:
    def __init__(self, **kwargs):
        self.host = kwargs.get('host', 'localhost')
        self.port = kwargs.get('port', 3306)
        self.username = kwargs.get('username', 'user')
        self.password = kwargs.get('password', 'pass')
        self.db = kwargs.get('db', 'driving_data')

from config.logging_setup import get_logger
logger = get_logger(__name__)

class DataProcessingPipeline:
    """数据处理完整流水线，集成各基础模块"""
    
    def __init__(self, config):
        # 初始化配置
        self.config = config
        
        # 初始化缓冲区管理器
        self.buffer_manager = BufferManager(
            buffer_size=config.get("buffer_size", 50000),
            persist_threshold=config.get("persist_threshold", 10000)
        )
        
        # 初始化数据存储
        redis_config = RedisConfig(**config.get("redis", {}))
        mysql_config = MySQLConfig(** config.get("mysql", {}))
        self.data_storage = DataStorage(redis_config, mysql_config)
        
        # 初始化驾驶行为分析器
        self.analyzer = BasicDrivingAnalyzer(
            thresholds=config.get("driving_thresholds")
        )
        
        # 同步分析器与存储的阈值配置
        self._sync_thresholds()
        
        # 数据读取器（延迟初始化，根据输入类型选择）
        self.data_reader = None
        
        # 连接配置更新信号
        self.data_storage.config_updated_signal.connect(self._on_config_updated)
        
        logger.info("数据处理流水线初始化完成")

    def _sync_thresholds(self):
        """同步分析器与存储的阈值配置"""
        try:
            storage_thresholds = self.data_storage.get_all_thresholds()
            if storage_thresholds:
                # 检查分析器是否有update_config方法
                if hasattr(self.analyzer, 'update_config'):
                    self.analyzer.update_config(thresholds=storage_thresholds)
                    logger.info("已同步驾驶行为阈值配置")
                else:
                    logger.warning("分析器不支持动态更新配置")
        except Exception as e:
            logger.warning(f"同步阈值配置时出错: {e}")

    def _on_config_updated(self):
        """配置更新回调"""
        self._sync_thresholds()
        logger.info("配置已更新，重新同步阈值")

    def setup_reader(self, reader_type, **kwargs):
        """设置数据读取器"""
        # 使用ProtoSerialDataReader
        reader_map = {
            "serial": ProtoSerialDataReader,
            "file": FileDataReader,
            "mqtt": MQTTClient
        }
        
        if reader_type not in reader_map:
            raise ValueError(f"不支持的数据读取类型: {reader_type}")
            
        # 停止现有读取器
        if self.data_reader:
            self.data_reader.stop()
            
        # 创建新读取器
        self.data_reader = reader_map[reader_type](** kwargs)
        self.data_reader.set_logger(logger.info)
        
        logger.info(f"已设置{reader_type}数据读取器")
        return self.data_reader

    def start(self):
        """启动数据处理流水线"""
        if not self.data_reader:
            raise RuntimeError("请先设置数据读取器")
            
        # 启动读取器并设置数据处理回调
        self.data_reader.start(callback=self._process_data)
        logger.info("数据处理流水线已启动")

    def stop(self):
        """停止数据处理流水线"""
        if self.data_reader:
            self.data_reader.stop()
            
        self.data_storage.close_connections()
        self.buffer_manager.clear_all()
        logger.info("数据处理流水线已停止")

    def _process_data(self, raw_data):
        """处理单条数据的完整流程"""
        try:
            # 1. 数据解析（如果读取器未内置解析）
            parsed_data = IMUDataParser().parse_line(raw_data)
            if not parsed_data:
                logger.warning("数据解析失败")
                return
                
            # 2. 添加到缓冲区
            self.buffer_manager.add_data(parsed_data)
            
            # 3. 驾驶行为分析
            analysis_result = self.analyzer.analyze_data(parsed_data)
            
            # 4. 数据存储
            self.data_storage.store_driving_data(analysis_result)
            
            # 5. 如果有检测到行为事件，触发事件处理
            if analysis_result["behaviors"]:
                self._handle_behavior_event(analysis_result)
                
        except Exception as e:
            logger.error(f"数据处理出错: {str(e)}")

    def _handle_behavior_event(self, event_data):
        """处理检测到的驾驶行为事件"""
        # 存储行为事件
        self.data_storage.store_behavior_event(event_data)
        
        # 可以在这里添加其他事件处理逻辑，如实时告警等
        logger.info(f"检测到驾驶行为事件: {event_data['behaviors']}")

    def get_recent_analysis(self, count=100):
        """获取最近的分析结果"""
        recent_data = self.buffer_manager.get_recent_data(count)
        return [self.analyzer.analyze_data(data) for data in recent_data]


# 使用示例
if __name__ == "__main__":
    # 配置示例
    pipeline_config = {
        "buffer_size": 50000,
        "persist_threshold": 10000,
        "redis": {
            "host": "localhost",
            "port": 6379,
            "db": 0
        },
        "mysql": {
            "host": "localhost",
            "port": 3306,
            "username": "user",
            "password": "pass",
            "db": "driving_data"
        },
        "driving_thresholds": {
            "max_acceleration": 4.5,
            "max_deceleration": -8.5,
            "speeding_threshold": 3.5
        }
    }
    
    # 创建并启动流水线
    pipeline = DataProcessingPipeline(pipeline_config)
    
    # 设置串口读取器（也可以是文件或MQTT读取器）
    pipeline.setup_reader(
        reader_type="serial",
        port="/dev/ttyUSB0",
        baud_rate=115200,
        flow_control="none"
    )
    
    # 启动处理流程
    try:
        pipeline.start()
        while True:
            input("按Enter键停止...\n")
            break
    finally:
        pipeline.stop()
