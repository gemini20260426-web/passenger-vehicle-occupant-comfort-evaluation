#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析脚本管理器
提供智能提取、加载和管理数据解析脚本的功能
"""

import os
import sys
import importlib
import inspect
import logging
from typing import Dict, List, Optional, Type, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from .script_analyzer import ScriptAnalyzer, ScriptGenerator, ScriptFeatures
    ANALYZER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"脚本分析器不可用: {e}")
    ANALYZER_AVAILABLE = False


class ParserInfo:
    """解析器信息类"""
    
    def __init__(self, name: str, description: str, class_name: str, 
                 module_path: str, supported_types: List[str]):
        self.name = name
        self.description = description
        self.class_name = class_name
        self.module_path = module_path
        self.supported_types = supported_types
        self.parser_class = None
        self.is_loaded = False
    
    def __str__(self):
        return f"{self.name}: {self.description}"


class ParserManager:
    """解析脚本管理器"""
    
    # 已知的解析器映射
    PARSER_MAP = {
        "CNAP数据解析器": {
            "module": "cnap_parser",
            "class": "CNAPDataParser",
            "description": "专门用于解析CNAP生理传感器数据，提供标准化的输出格式",
            "supported_types": ["CNAP", "血压", "生理数据"]
        },
        "IMU数据解析器": {
            "module": "data_parser",
            "class": "IMUDataParser",
            "description": "IMU数据统一解析器，处理文件和串口数据",
            "supported_types": ["IMU", "惯性传感器", "加速度", "陀螺仪"]
        },
        "心血管数据解析器": {
            "module": "cardiovascular_parser",
            "class": "CardiovascularDataParser",
            "description": "专门用于解析CNAP（连续无创血压）等心血管监测数据",
            "supported_types": ["心血管", "血压", "CNAP", "心率"]
        },
        "CAN全量数据解析器": {
            "module": "can_parser_v2",
            "class": "CANFullParser",
            "description": "全量多通道CAN数据解析器，支持ch1~ch5六轴IMU + ch6车机信号，41字段输出",
            "supported_types": ["CAN", "CANFull", "CAN总线", "CAN网关", "车辆CAN"]
        }
    }
    
    def __init__(self, parsers_dir: Optional[str] = None):
        """初始化解析脚本管理器
        
        Args:
            parsers_dir: 解析脚本所在目录，默认为当前目录
        """
        if parsers_dir is None:
            parsers_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.parsers_dir = Path(parsers_dir)
        self.parsers: Dict[str, ParserInfo] = {}
        self.loaded_parsers: Dict[str, Any] = {}
        
        # 初始化已知解析器
        self._init_known_parsers()
        
        # 扫描并自动发现解析器
        self._discover_parsers()
        
        logger.info(f"解析脚本管理器初始化完成，共发现 {len(self.parsers)} 个解析器")
    
    def _init_known_parsers(self):
        """初始化已知解析器"""
        for name, info in self.PARSER_MAP.items():
            parser_info = ParserInfo(
                name=name,
                description=info["description"],
                class_name=info["class"],
                module_path=info["module"],
                supported_types=info["supported_types"]
            )
            self.parsers[name] = parser_info
    
    def _discover_parsers(self):
        """自动发现目录中的解析脚本"""
        try:
            if not self.parsers_dir.exists():
                logger.warning(f"解析脚本目录不存在: {self.parsers_dir}")
                return
            
            # 扫描目录中的Python文件
            for file_path in self.parsers_dir.glob("*.py"):
                if file_path.name.startswith("__"):
                    continue
                
                try:
                    self._analyze_parser_file(file_path)
                except Exception as e:
                    logger.debug(f"分析解析文件失败 {file_path.name}: {e}")
                    
        except Exception as e:
            logger.error(f"发现解析脚本失败: {e}")
    
    def _analyze_parser_file(self, file_path: Path):
        """分析解析脚本文件并提取信息
        
        Args:
            file_path: 解析脚本文件路径
        """
        file_name = file_path.stem
        
        # 跳过已添加的解析器
        existing_names = [info.module_path for info in self.parsers.values()]
        if file_name in existing_names:
            return
        
        # 过滤非解析器文件
        skip_keywords = [
            'buffer', 'manager', 'pipeline', 'adapter', 'config', 
            'reader', 'storage', 'sync', 'evaluation', 'influx',
            'protocol', 'proto', 'serial', 'file', 'integration',
            'unified', 'utils', 'common', 'base', 'bak', 'backup',
            'autogen'
        ]
        if any(keyword in file_name.lower() for keyword in skip_keywords):
            logger.debug(f"跳过非解析器文件: {file_path.name}")
            return
        
        try:
            # 读取文件内容进行分析
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查文件是否包含解析器类
            has_parser_class = self._has_parser_class(content)
            if not has_parser_class:
                logger.debug(f"文件 {file_path.name} 不包含解析器类，跳过")
                return
            
            # 简单分析文件内容
            parser_name = self._extract_parser_name(content, file_name)
            description = self._extract_description(content)
            class_name = self._extract_class_name(content)
            supported_types = self._extract_supported_types(content, class_name)
            
            if class_name and parser_name:
                parser_info = ParserInfo(
                    name=parser_name,
                    description=description or f"{parser_name} 数据解析器",
                    class_name=class_name,
                    module_path=file_name,
                    supported_types=supported_types
                )
                
                # 检查是否与现有解析器重名
                if parser_name not in self.parsers:
                    self.parsers[parser_name] = parser_info
                    logger.info(f"发现新解析器: {parser_name}")
                    
        except Exception as e:
            logger.debug(f"分析文件 {file_path.name} 失败: {e}")
    
    def _has_parser_class(self, content: str) -> bool:
        """检查文件内容是否包含解析器类
        
        Args:
            content: 文件内容
            
        Returns:
            是否包含解析器类
        """
        # 检查常见的解析器类名模式
        parser_patterns = [
            r'class\s+\w*Parser\s*',
            r'class\s+\w*Analyzer\s*',
            r'class\s+\w*Processor\s*',
            r'class\s+IMU',
            r'class\s+CNAP',
            r'class\s+Cardiovascular'
        ]
        
        import re
        for pattern in parser_patterns:
            if re.search(pattern, content):
                return True
        
        return False
    
    def _extract_parser_name(self, content: str, file_name: str) -> str:
        """从文件内容中提取解析器名称"""
        if "cnap" in file_name.lower():
            return "CNAP数据解析器"
        elif "imu" in file_name.lower():
            return "IMU数据解析器"
        elif "cardiovascular" in file_name.lower() or "blood" in file_name.lower():
            return "心血管数据解析器"
        else:
            return f"{file_name} 数据解析器"
    
    def _extract_description(self, content: str) -> Optional[str]:
        """从文件内容中提取描述"""
        import re
        doc_match = re.search(r'\"\"\"(.*?)\"\"\"', content, re.DOTALL)
        if doc_match:
            return doc_match.group(1).strip()
        return None
    
    def _extract_class_name(self, content: str) -> Optional[str]:
        """从文件内容中提取解析器类名"""
        import re
        class_matches = re.findall(r'class\s+(\w+Parser)\s*:', content)
        if class_matches:
            return class_matches[0]
        class_matches = re.findall(r'class\s+(\w+)\s*:', content)
        for cls_name in class_matches:
            if "Parser" in cls_name:
                return cls_name
        return class_matches[0] if class_matches else None
    
    def _extract_supported_types(self, content: str, class_name: str) -> List[str]:
        """提取支持的数据类型"""
        supported = []
        
        class_name_lower = class_name.lower() if class_name else ""
        if "cnap" in class_name_lower or "blood" in class_name_lower or "cardiovascular" in class_name_lower:
            supported.extend(["CNAP", "血压", "生理数据", "心血管"])
        elif "imu" in class_name_lower or "inertial" in class_name_lower:
            supported.extend(["IMU", "惯性传感器", "加速度", "陀螺仪"])
        else:
            supported.extend(["通用", "文本", "CSV"])
        
        return supported
    
    def get_available_parsers(self) -> List[ParserInfo]:
        """获取所有可用的解析器
        
        Returns:
            解析器信息列表
        """
        return list(self.parsers.values())
    
    def get_parser_by_name(self, name: str) -> Optional[ParserInfo]:
        """通过名称获取解析器信息
        
        Args:
            name: 解析器名称
            
        Returns:
            解析器信息对象，如果找不到则返回None
        """
        return self.parsers.get(name)
    
    def get_parsers_by_type(self, data_type: str) -> List[ParserInfo]:
        """根据数据类型获取适用的解析器
        
        Args:
            data_type: 数据类型
            
        Returns:
            适用的解析器列表
        """
        data_type_lower = data_type.lower()
        matching_parsers = []
        
        for parser_info in self.parsers.values():
            for supported_type in parser_info.supported_types:
                if supported_type.lower() in data_type_lower or data_type_lower in supported_type.lower():
                    matching_parsers.append(parser_info)
                    break
        
        # 如果没有找到匹配，返回所有解析器
        if not matching_parsers:
            return list(self.parsers.values())
        
        return matching_parsers
    
    def smart_detect_parser(self, file_path: Optional[str] = None, 
                           data_content: Optional[str] = None,
                           data_type: Optional[str] = None) -> Optional[ParserInfo]:
        """智能检测适用的解析器
        
        Args:
            file_path: 文件路径
            data_content: 数据内容
            data_type: 数据类型
            
        Returns:
            推荐的解析器信息，如果无法推荐则返回None
        """
        # 优先根据数据类型匹配
        if data_type:
            matching_parsers = self.get_parsers_by_type(data_type)
            if matching_parsers:
                logger.info(f"根据数据类型 '{data_type}' 推荐解析器: {matching_parsers[0].name}")
                return matching_parsers[0]
        
        # 根据数据内容匹配（优先于文件名，内容更可靠）
        if data_content:
            content_lower = data_content.lower()
            # 把CAN检查放在最前面！因为CAN数据特征非常强！
            if self._is_can_content(data_content):
                parser = self.get_parser_by_name("CAN全量数据解析器")
                if parser:
                    return parser
            elif "cnap" in content_lower or "systolic" in content_lower or "diastolic" in content_lower:
                parser = self.get_parser_by_name("CNAP数据解析器")
                if parser:
                    return parser
            elif self._is_imu_content(data_content):
                parser = self.get_parser_by_name("IMU数据解析器")
                if parser:
                    return parser
        
        # 根据文件名匹配（回退）
        if file_path:
            file_name = os.path.basename(file_path).lower()
            file_ext = os.path.splitext(file_name)[1].lower()
            
            if "imu" in file_name or "inertial" in file_name:
                parser = self.get_parser_by_name("IMU数据解析器")
                if parser:
                    return parser
            elif "cnap" in file_name or "blood" in file_name:
                parser = self.get_parser_by_name("CNAP数据解析器")
                if parser:
                    return parser
        
        # 默认返回第一个解析器
        if self.parsers:
            return list(self.parsers.values())[0]
        
        return None

    @staticmethod
    def _is_can_content(data_content: str) -> bool:
        can_indicators = [
            'CAN通道', '帧类型', '帧格式', 'ID号', 'CAN类型',
            'CANID', 'can_id', 'canid', 'signal_name',
            '0x1FFF0051', '0x1FFF0053',
            '0x100', '0x101', '0x102', '0x103',
            '0x51000', '0x1F01', '0x1F02', '0x6100',
            '车速', '方向盘转角', '急刹', '刹车油压',
        ]
        content_for_check = data_content[:5000]
        content_lower = content_for_check.lower()
        
        # 检查CAN特有标识符
        for indicator in can_indicators:
            if indicator in content_for_check:
                return True
        
        # 检查CSV表头模式（can_id列是CAN数据的强特征）
        lines = content_for_check.split('\n')
        for line in lines[:5]:
            striped = line.strip()
            if striped.startswith('序号,') and 'CAN通道' in striped:
                return True
            if striped.startswith('idx,') and 'channel' in striped.lower():
                return True
            # 检查是否包含can_id列（CAN数据的强特征）
            if 'can_id' in striped.lower():
                return True
            # 检查是否包含时间戳+CAN ID模式
            if 'timestamp' in striped.lower() and ('can_id' in striped.lower() or '0x' in striped):
                return True
        
        # 检查通道+十六进制组合特征
        has_ch = False
        has_hex = False
        has_can_id = False
        for line in lines[:30]:
            if not has_ch and ('ch1' in line or 'ch3' in line or 'ch4' in line or 'ch5' in line or 'ch6' in line):
                has_ch = True
            if not has_hex and ('0x1FFF' in line or '0x100' in line or '0x101' in line or '0x102' in line or '0x103' in line):
                has_hex = True
            if not has_can_id and ('can_id' in line.lower() or 'signal_name' in line.lower()):
                has_can_id = True
            if has_ch and has_hex:
                return True
            if has_can_id:
                return True
        
        # 检查综合特征
        if 'ch1' in content_for_check and 'ch6' in content_for_check and '0x' in content_for_check:
            return True
        
        # 检查是否有多行包含CAN ID模式（如 0x100, 0x101 等）
        can_id_count = 0
        for line in lines[:50]:
            if '0x100' in line or '0x101' in line or '0x102' in line or '0x103' in line:
                can_id_count += 1
        if can_id_count >= 3:
            return True
        
        return False

    @staticmethod
    def _is_imu_content(data_content: str) -> bool:
        """检测是否为IMU数据内容
        
        IMU数据特征：
        1. 包含特定字段名：ax, ay, az, gx, gy, gz, accel, gyro, imu等
        2. 包含时间戳格式（方括号包裹的日期时间）
        3. 包含AA和BB十六进制标记，且符合IMU数据格式模式
        4. 不包含CAN特有标识符（避免与CAN数据混淆）
        """
        content_for_check = data_content[:3000]
        content_lower = content_for_check.lower()
        lines = content_for_check.split('\n')
        
        # 首先检查是否有CAN特征，如果有则排除IMU
        if ParserManager._is_can_content(data_content):
            return False
        
        # IMU特有字段标识符
        imu_fields = ['ax', 'ay', 'az', 'gx', 'gy', 'gz', 
                      'accel_x', 'accel_y', 'accel_z',
                      'gyro_x', 'gyro_y', 'gyro_z',
                      'imu', 'inertial', 'acceleration', 'gyroscope']
        
        # 检查是否包含IMU字段
        has_imu_fields = any(field in content_lower for field in imu_fields)
        
        # 检查是否包含时间戳格式（IMU数据通常以时间戳开头）
        has_timestamp = False
        for line in lines[:10]:
            # IMU时间戳格式：[2025-04-17 12:51:33-577]
            if line.startswith('[') and ('-' in line or ':' in line):
                has_timestamp = True
                break
        
        # 检查是否包含AA和BB标记（IMU数据帧的起始和结束标记）
        # 但要求AA和BB之间有特定模式（数字、逗号等）
        has_aa_bb = False
        if 'AA' in content_for_check and 'BB' in content_for_check:
            # 检查AA和BB是否在合理的位置（不是在十六进制数据中间）
            # IMU数据格式：[时间戳] AAxxxxx,数值,数值,...,BBxxxx
            for line in lines[:10]:
                if 'AA' in line and 'BB' in line:
                    aa_pos = line.find('AA')
                    bb_pos = line.find('BB')
                    # AA应该在前面，BB应该在后面，且中间有内容
                    if aa_pos < bb_pos and (bb_pos - aa_pos) > 5:
                        has_aa_bb = True
                        break
        
        # 检查是否有多行符合IMU数据格式
        imu_line_count = 0
        for line in lines[:20]:
            line_strip = line.strip()
            # IMU数据行特征：以时间戳开头，包含逗号分隔的数值
            if line_strip.startswith('[') and ',' in line_strip:
                parts = line_strip.split(',')
                # 典型IMU数据有6-12个字段
                if 6 <= len(parts) <= 15:
                    imu_line_count += 1
        
        # 判断逻辑：满足以下条件之一即可认为是IMU数据
        # 1. 包含IMU字段名 + 时间戳格式
        # 2. 包含AA/BB标记且符合IMU格式模式
        # 3. 有多行符合IMU数据格式
        # 4. 纯CSV表头包含多个IMU字段（没有时间戳的情况）
        
        condition1 = has_imu_fields and has_timestamp
        condition2 = has_aa_bb and has_timestamp
        condition3 = imu_line_count >= 3
        
        # 统计IMU字段数量（用于纯CSV表头情况）
        imu_field_count = sum(1 for field in imu_fields if field in content_lower)
        condition4 = imu_field_count >= 4  # 至少包含4个IMU字段
        
        return condition1 or condition2 or condition3 or condition4

    def load_parser(self, parser_name: str) -> Optional[Any]:
        """加载指定的解析器
        
        Args:
            parser_name: 解析器名称
            
        Returns:
            解析器实例，如果加载失败则返回None
        """
        try:
            if parser_name in self.loaded_parsers:
                logger.debug(f"解析器已加载: {parser_name}")
                return self.loaded_parsers[parser_name]

            parser_info = self.parsers.get(parser_name)
            if not parser_info:
                logger.error(f"找不到解析器: {parser_name}")
                return None

            module_path = parser_info.module_path

            if os.path.isabs(module_path):
                import importlib.util as _loader_util
                unique_name = f"_custom_parser_{parser_info.class_name}_{hash(module_path) % 100000}"
                spec = _loader_util.spec_from_file_location(unique_name, module_path)
                if spec is None or spec.loader is None:
                    logger.error(f"无法为自定义解析器创建加载规范: {module_path}")
                    return None
                module = _loader_util.module_from_spec(spec)
                spec.loader.exec_module(module)
            else:
                if not module_path.startswith('.'):
                    module_path = '.' + module_path
                try:
                    module = importlib.import_module(module_path, package=__package__)
                except (TypeError, ImportError):
                    full_path = os.path.join(str(self.parsers_dir), parser_info.module_path)
                    if not full_path.endswith('.py'):
                        full_path += '.py'
                    import importlib.util as _loader_util
                    unique_name = f"_parser_{parser_info.class_name}_{hash(full_path) % 100000}"
                    spec = _loader_util.spec_from_file_location(unique_name, full_path)
                    if spec is None or spec.loader is None:
                        logger.error(f"无法为解析器创建加载规范: {full_path}")
                        return None
                    module = _loader_util.module_from_spec(spec)
                    spec.loader.exec_module(module)

            parser_class = getattr(module, parser_info.class_name, None)
            if not parser_class:
                logger.error(f"在模块 {parser_info.module_path} 中找不到类 {parser_info.class_name}")
                return None

            parser_instance = parser_class()
            parser_info.is_loaded = True
            parser_info.parser_class = parser_class

            self.loaded_parsers[parser_name] = parser_instance

            logger.info(f"成功加载解析器: {parser_name}")
            return parser_instance

        except Exception as e:
            logger.error(f"加载解析器 {parser_name} 失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def validate_parser(self, parser_name: str, sample_data: str = None) -> Tuple[bool, str]:
        """验证解析器是否正常工作
        
        Args:
            parser_name: 解析器名称
            sample_data: 测试样本数据
            
        Returns:
            (是否有效, 错误信息)
        """
        try:
            parser = self.load_parser(parser_name)
            if not parser:
                return False, "无法加载解析器"
            
            # 检查是否有必需的方法
            required_methods = ['parse_line', 'parse_file']
            has_methods = False
            for method in required_methods:
                if hasattr(parser, method) and callable(getattr(parser, method)):
                    has_methods = True
                    break
            
            if not has_methods:
                return False, "解析器缺少必需的解析方法"
            
            return True, "解析器验证通过"
            
        except Exception as e:
            logger.error(f"验证解析器 {parser_name} 失败: {e}")
            return False, str(e)
    
    def add_custom_parser(self, file_path: str) -> Optional[str]:
        """添加自定义解析脚本
        
        Args:
            file_path: 自定义解析脚本文件路径
            
        Returns:
            解析器名称，如果添加失败则返回None
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"文件不存在: {file_path}")
                return None

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            import re
            class_matches = re.findall(r'class\s+(\w+)\s*[:\(]', content)
            parser_class_name = None
            for cls_name in class_matches:
                if 'Parser' in cls_name or 'parser' in cls_name.lower():
                    parser_class_name = cls_name
                    break
            if not parser_class_name and class_matches:
                parser_class_name = class_matches[0]

            if not parser_class_name:
                logger.error(f"文件中未找到解析器类: {file_path}")
                return None

            desc_match = re.search(r'\"\"\"(.*?)\"\"\"', content, re.DOTALL)
            description = desc_match.group(1).strip().replace('\n', ' ') if desc_match else f"{path.stem} 数据解析器"

            # 根据文件名检测支持类型
            supported_types = ["通用"]
            stem_lower = path.stem.lower()
            if 'cnap' in stem_lower or 'blood' in stem_lower or 'cardiovascular' in stem_lower:
                supported_types = ["CNAP", "血压", "生理数据", "波形"]
            elif 'imu' in stem_lower or 'inertial' in stem_lower:
                supported_types = ["IMU", "惯性传感器", "加速度", "陀螺仪"]

            parser_name = f"{path.stem} (自定义)"

            # 直接添加到 parsers，覆盖可能存在的同名项
            self.parsers[parser_name] = ParserInfo(
                name=parser_name,
                description=description,
                class_name=parser_class_name,
                module_path=str(path.absolute()),
                supported_types=supported_types,
            )

            logger.info(f"成功添加自定义解析器: {parser_name} → {parser_class_name}")
            return parser_name

        except Exception as e:
            logger.error(f"添加自定义解析器失败: {e}")
            return None
    
    def refresh_parsers(self):
        """刷新解析器列表"""
        logger.info("刷新解析器列表...")
        self.parsers.clear()
        self.loaded_parsers.clear()
        self._init_known_parsers()
        self._discover_parsers()
        logger.info(f"刷新完成，共 {len(self.parsers)} 个解析器")


# 单例实例
_parser_manager: Optional[ParserManager] = None


def get_parser_manager() -> ParserManager:
    """获取解析脚本管理器单例
    
    Returns:
        ParserManager 实例
    """
    global _parser_manager
    if _parser_manager is None:
        _parser_manager = ParserManager()
    return _parser_manager


def reset_parser_manager():
    """重置解析脚本管理器"""
    global _parser_manager
    _parser_manager = None


def smart_generate_parser(reference_script: str, 
                          custom_name: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """智能生成解析脚本
    
    Args:
        reference_script: 参考脚本路径
        custom_name: 自定义名称
        
    Returns:
        (新脚本路径, 解析器名称)
    """
    if not ANALYZER_AVAILABLE:
        logger.error("脚本分析器不可用")
        return None, None
    
    try:
        from .script_analyzer import analyze_and_generate
        
        logger.info(f"开始分析参考脚本: {reference_script}")
        
        # 分析并生成脚本
        output_path, class_name = analyze_and_generate(
            reference_script,
            output_dir=Path(__file__).parent,
            custom_name=custom_name
        )
        
        logger.info(f"脚本生成成功: {output_path}")
        
        # 获取新的解析器名称
        script_name = Path(output_path).stem
        parser_name = f"{script_name.replace('_autogen', '')} (智能生成)"
        
        # 刷新管理器
        reset_parser_manager()
        mgr = get_parser_manager()
        
        # 查找新生成的解析器
        for name, info in mgr.parsers.items():
            if info.module_path == script_name:
                logger.info(f"新解析器已注册: {name}")
                return output_path, name
        
        return output_path, parser_name
        
    except Exception as e:
        logger.error(f"智能生成解析器失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None, None


def preview_parsed_features(reference_script: str) -> Optional[Dict[str, Any]]:
    """预览解析脚本的特征
    
    Args:
        reference_script: 参考脚本路径
        
    Returns:
        特征字典
    """
    if not ANALYZER_AVAILABLE:
        return None
    
    try:
        from .script_analyzer import ScriptAnalyzer
        
        analyzer = ScriptAnalyzer()
        features = analyzer.analyze_script(reference_script)
        
        return {
            'script_name': features.script_name,
            'data_types': features.data_types,
            'parse_patterns': features.parse_patterns,
            'field_extractors': features.field_extractors,
            'class_name': features.class_name,
            'base_parser_type': features.base_parser_type,
            'file_extensions': features.file_extensions,
            'source_fields': features.source_fields
        }
        
    except Exception as e:
        logger.error(f"预览解析特征失败: {e}")
        return None


def smart_generate_parser_with_fields(reference_script: str, 
                                       custom_name: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[List[Dict[str, str]]]]:
    """智能生成解析器并返回字段信息
    
    Args:
        reference_script: 参考脚本路径
        custom_name: 自定义名称
        
    Returns:
        (新脚本路径, 解析器名称, 源字段列表)
    """
    source_fields = None
    if ANALYZER_AVAILABLE:
        try:
            from .script_analyzer import ScriptAnalyzer
            analyzer = ScriptAnalyzer()
            features = analyzer.analyze_script(reference_script)
            source_fields = features.source_fields
        except Exception as e:
            logger.warning(f"提取字段信息失败: {e}")
    
    # 调用原有的生成函数
    output_path, parser_name = smart_generate_parser(reference_script, custom_name)
    
    return output_path, parser_name, source_fields
