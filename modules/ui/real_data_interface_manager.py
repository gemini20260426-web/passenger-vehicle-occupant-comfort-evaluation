# -*- coding: utf-8 -*-
"""
真实数据接口管理器
连接Core系统与UI的桥梁，替代所有模拟数据
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from collections import deque
from PySide6.QtCore import QObject, Signal, QTimer

# 添加项目根路径，使用完整包路径导入
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# 使用纯内存缓存（避免磁盘I/O阻塞UI）
HAS_DISK_CACHE = False

class RealDataInterfaceManager(QObject):
    """连接Core系统与UI的桥梁"""
    
    # 数据更新信号
    imu_data_updated = Signal(dict)
    cnap_data_updated = Signal(dict)
    analysis_result_updated = Signal(dict)
    system_status_updated = Signal(dict)
    sync_status_updated = Signal(dict)
    
    # 错误信号
    data_error_occurred = Signal(str, str)
    connection_status_changed = Signal(bool, str)
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Core系统模块引用
        self.multi_source_sync = None
        self.imu_parser = None
        self.cnap_parser = None
        self.basic_analyzer = None
        self.advanced_analyzer = None
        
        # 连接状态
        self.is_connected = False
        self.connection_error = None
        
        # 数据缓存 - 使用纯内存缓存避免磁盘I/O阻塞UI
        self.data_cache = {
            'imu': deque(maxlen=100),
            'cnap': deque(maxlen=100),
            'analysis': deque(maxlen=50),
            'system': {}
        }
        
        # 定时器用于数据更新
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_data)
        
        # 初始化Core系统连接
        self._init_core_connection()
        
    def _init_core_connection(self):
        """初始化Core系统连接"""
        try:
            self.logger.info("🔗 开始连接Core系统...")
            
            self._import_core_modules()
            self._ensure_placeholder_fallback()
            
            if self._establish_connection():
                self.is_connected = True
                self.connection_status_changed.emit(True, "Core系统连接成功")
                self.logger.info("✅ Core系统连接成功")
                
                self.update_timer.start(2000)
            else:
                self.connection_error = "无法建立Core系统连接"
                self.connection_status_changed.emit(False, self.connection_error)
                self.logger.error(f"❌ {self.connection_error}")
                
        except Exception as e:
            self.connection_error = f"Core系统连接失败: {str(e)}"
            self.connection_status_changed.emit(False, self.connection_error)
            self.logger.error(f"❌ {self.connection_error}")

    def _ensure_placeholder_fallback(self):
        """为导入失败的模块创建占位回退"""
        self._create_placeholder_modules()
    
    def _import_core_modules(self):
        """从 ServiceLocator 获取已初始化的核心模块"""
        try:
            from core.core.service_locator import ServiceLocator
            locator = ServiceLocator()

            self.multi_source_sync = locator.get('multi_source_sync_engine')
            self.basic_analyzer = locator.get('basic_analyzer')
            self.data_bridge = locator.get('data_bridge')
            
            # 尝试获取 IMU 和 CNAP 解析器（如果已注册）
            self.imu_parser = locator.get('imu_parser')
            self.cnap_parser = locator.get('cnap_parser')

            if self.multi_source_sync:
                self.logger.info("多源同步引擎已从 ServiceLocator 获取")
            if self.basic_analyzer:
                self.logger.info("基础分析器已从 ServiceLocator 获取")
            if self.data_bridge:
                self.logger.info("DataBridge 已从 ServiceLocator 获取")
            if self.imu_parser:
                self.logger.info("IMU 解析器已从 ServiceLocator 获取")
            if self.cnap_parser:
                self.logger.info("CNAP 解析器已从 ServiceLocator 获取")
        except Exception as e:
            self.logger.warning("从 ServiceLocator 获取核心模块失败: %s", e)
    
    def _create_placeholder_modules(self):
        """创建占位模块，确保系统不会崩溃"""
        class PlaceholderModule:
            def __init__(self, name):
                self.name = name
                self.logger = logging.getLogger(__name__)
                self._warned = False
                self.is_placeholder = True
                
            def get_latest_data(self):
                if not self._warned:
                    self.logger.warning(f"⚠️ {self.name} 使用占位数据")
                    self._warned = True
                return {}
                
            def start_processing(self):
                return False
        
        # 创建占位模块
        if not self.multi_source_sync:
            self.multi_source_sync = PlaceholderModule("MultiSourceDataSyncManager")
        if not self.imu_parser:
            self.imu_parser = PlaceholderModule("IMUDataParser")
        if not self.cnap_parser:
            self.cnap_parser = PlaceholderModule("CNAPDataParser")
        if not self.basic_analyzer:
            self.basic_analyzer = PlaceholderModule("BasicDrivingAnalyzer")
        if not self.advanced_analyzer:
            self.advanced_analyzer = PlaceholderModule("AdvancedBehaviorAnalyzer")
    
    def _establish_connection(self):
        """建立Core系统连接"""
        try:
            # 检查模块是否可用
            if hasattr(self.multi_source_sync, 'start_processing'):
                self.multi_source_sync.start_processing()
            
            if hasattr(self.imu_parser, 'start_processing'):
                self.imu_parser.start_processing()
                
            if hasattr(self.cnap_parser, 'start_processing'):
                self.cnap_parser.start_processing()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 建立连接失败: {e}")
            return False

    @property
    def has_real_data(self) -> bool:
        """检查是否所有核心模块都使用真实数据（非占位）"""
        modules = [
            self.multi_source_sync,
            self.imu_parser,
            self.cnap_parser,
            self.basic_analyzer,
            self.advanced_analyzer,
        ]
        return all(
            m is not None and not getattr(m, 'is_placeholder', False)
            for m in modules
        )

    def get_module_status(self) -> Dict[str, Dict[str, Any]]:
        """获取各模块状态详情"""
        status = {}
        for attr_name in ['multi_source_sync', 'imu_parser', 'cnap_parser',
                           'basic_analyzer', 'advanced_analyzer']:
            module = getattr(self, attr_name, None)
            if module is None:
                status[attr_name] = {'loaded': False, 'is_placeholder': True, 'error': '模块为None'}
            elif getattr(module, 'is_placeholder', False):
                status[attr_name] = {'loaded': False, 'is_placeholder': True, 'error': '使用占位模块'}
            else:
                status[attr_name] = {'loaded': True, 'is_placeholder': False, 'error': None}
        return status
    
    def _update_data(self):
        """定时更新数据"""
        if not self.is_connected:
            return
            
        try:
            # 更新IMU数据
            self._update_imu_data()
            
            # 更新CNAP数据
            self._update_cnap_data()
            
            # 更新分析结果
            self._update_analysis_data()
            
            # 更新系统状态
            self._update_system_status()
            
        except Exception as e:
            self.logger.error(f"❌ 数据更新失败: {e}")
            self.data_error_occurred.emit("数据更新失败", str(e))
    
    def _update_imu_data(self):
        """更新IMU数据"""
        try:
            if self.imu_parser and hasattr(self.imu_parser, 'get_latest_data'):
                data = self.imu_parser.get_latest_data()
                if data:
                    self.data_cache['imu'].append(data)
                    self.imu_data_updated.emit(data)
                    
        except Exception as e:
            self.logger.error(f"❌ IMU数据更新失败: {e}")
    
    def _update_cnap_data(self):
        """更新CNAP数据"""
        try:
            if self.cnap_parser and hasattr(self.cnap_parser, 'get_latest_data'):
                data = self.cnap_parser.get_latest_data()
                if data:
                    # 使用内存缓存
                    self.data_cache['cnap'].append(data)
                    
                    self.cnap_data_updated.emit(data)
                    
        except Exception as e:
            self.logger.error(f"❌ CNAP数据更新失败: {e}")
    
    def _update_analysis_data(self):
        """更新分析结果数据"""
        try:
            if self.basic_analyzer and hasattr(self.basic_analyzer, 'get_latest_results'):
                results = self.basic_analyzer.get_latest_results()
                if results:
                    # 使用内存缓存
                    self.data_cache['analysis'].append(results)
                    
                    self.analysis_result_updated.emit(results)
                    
        except Exception as e:
            self.logger.error(f"❌ 分析结果更新失败: {e}")
    
    def _update_system_status(self):
        """更新系统状态"""
        try:
            # 获取缓存数据量
            imu_count = len(self.data_cache['imu']) if hasattr(self.data_cache['imu'], '__len__') else 0
            cnap_count = len(self.data_cache['cnap']) if hasattr(self.data_cache['cnap'], '__len__') else 0
            analysis_count = len(self.data_cache['analysis']) if hasattr(self.data_cache['analysis'], '__len__') else 0
            
            status = {
                'timestamp': self._get_current_timestamp(),
                'connection_status': self.is_connected,
                'data_rate': {
                    'imu': imu_count,
                    'cnap': cnap_count,
                    'analysis': analysis_count
                },
                'error_count': 0
            }
            
            self.data_cache['system'] = status
            self.system_status_updated.emit(status)
            
        except Exception as e:
            self.logger.error(f"❌ 系统状态更新失败: {e}")
    
    def _get_current_timestamp(self):
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    # 公共接口方法
    def get_real_time_data(self, data_type: str) -> Dict[str, Any]:
        """获取实时数据，替代模拟数据"""
        try:
            if data_type == "imu":
                cache = self.data_cache['imu']
                return cache[-1] if cache else {}
            elif data_type == "cnap":
                cache = self.data_cache['cnap']
                return cache[-1] if cache else {}
            elif data_type == "analysis":
                cache = self.data_cache['analysis']
                return cache[-1] if cache else {}
            elif data_type == "system":
                return self.data_cache['system']
            else:
                self.logger.warning(f"⚠️ 未知数据类型: {data_type}")
                return {}
                
        except Exception as e:
            self.logger.error(f"❌ 获取数据失败: {e}")
            return {}
    
    def get_historical_data(self, data_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取历史数据"""
        try:
            if data_type in self.data_cache:
                data = self.data_cache[data_type]
                if isinstance(data, list):
                    return data[-limit:] if len(data) > limit else data
                else:
                    return [data]
            return []
            
        except Exception as e:
            self.logger.error(f"❌ 获取历史数据失败: {e}")
            return []
    
    def start_analysis(self, analysis_type: str, **kwargs) -> bool:
        """启动分析"""
        try:
            if analysis_type == "basic" and self.basic_analyzer:
                if hasattr(self.basic_analyzer, 'start_analysis'):
                    return self.basic_analyzer.start_analysis(**kwargs)
            elif analysis_type == "advanced" and self.advanced_analyzer:
                if hasattr(self.advanced_analyzer, 'start_analysis'):
                    return self.advanced_analyzer.start_analysis(**kwargs)
            
            self.logger.warning(f"⚠️ 不支持的分析类型: {analysis_type}")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 启动分析失败: {e}")
            return False
    
    def stop_analysis(self, analysis_type: str) -> bool:
        """停止分析"""
        try:
            if analysis_type == "basic" and self.basic_analyzer:
                if hasattr(self.basic_analyzer, 'stop_analysis'):
                    return self.basic_analyzer.stop_analysis()
            elif analysis_type == "advanced" and self.advanced_analyzer:
                if hasattr(self.advanced_analyzer, 'stop_analysis'):
                    return self.advanced_analyzer.stop_analysis()
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 停止分析失败: {e}")
            return False
    
    def get_connection_status(self) -> Dict[str, Any]:
        """获取连接状态"""
        return {
            'is_connected': self.is_connected,
            'error': self.connection_error,
            'modules': {
                'multi_source_sync': self.multi_source_sync is not None,
                'imu_parser': self.imu_parser is not None,
                'cnap_parser': self.cnap_parser is not None,
                'basic_analyzer': self.basic_analyzer is not None,
                'advanced_analyzer': self.advanced_analyzer is not None
            }
        }
    
    def reconnect(self) -> bool:
        """重新连接Core系统"""
        try:
            self.logger.info("🔄 尝试重新连接Core系统...")
            
            # 停止当前连接
            if self.update_timer.isActive():
                self.update_timer.stop()
            
            # 重新初始化连接
            self._init_core_connection()
            
            return self.is_connected
            
        except Exception as e:
            self.logger.error(f"❌ 重新连接失败: {e}")
            return False
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.update_timer.isActive():
                self.update_timer.stop()
            
            # 停止所有模块
            if self.multi_source_sync and hasattr(self.multi_source_sync, 'stop_processing'):
                self.multi_source_sync.stop_processing()
            
            if self.imu_parser and hasattr(self.imu_parser, 'stop_processing'):
                self.imu_parser.stop_processing()
                
            if self.cnap_parser and hasattr(self.cnap_parser, 'stop_processing'):
                self.cnap_parser.stop_processing()
            
            self.logger.info("✅ 资源清理完成")
            
        except Exception as e:
            self.logger.error(f"❌ 资源清理失败: {e}")
