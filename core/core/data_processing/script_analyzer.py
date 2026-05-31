#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能脚本分析器
分析参考解析脚本，提取特征，自动生成适配的解析脚本
"""

import ast
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ScriptFeatures:
    """解析脚本特征"""
    script_name: str
    data_types: List[str]
    parse_patterns: List[str]
    field_extractors: Dict[str, str]
    timestamp_logic: Optional[str]
    validation_logic: Optional[str]
    class_name: str
    base_parser_type: str
    file_extensions: List[str]
    source_fields: List[Dict[str, str]]  # 源字段信息列表: [{'source': 'ax', 'target': 'ax', 'type': 'float'}, ...]


class ScriptAnalyzer:
    """脚本分析器"""

    def __init__(self):
        self.features: Optional[ScriptFeatures] = None

    def analyze_script(self, script_path: str) -> ScriptFeatures:
        """分析解析脚本并提取特征

        Args:
            script_path: 脚本文件路径

        Returns:
            提取的脚本特征
        """
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.features = self._extract_features(script_path, content)
        return self.features

    def _extract_features(self, script_path: str, content: str) -> ScriptFeatures:
        """提取脚本特征"""
        tree = ast.parse(content)
        
        script_name = Path(script_path).stem
        
        # 提取类名
        class_name = self._extract_class_name(tree)
        
        # 提取数据类型
        data_types = self._extract_data_types(content)
        
        # 提取解析模式
        parse_patterns = self._extract_parse_patterns(content)
        
        # 提取字段提取器
        field_extractors = self._extract_field_extractors(tree)
        
        # 提取源字段列表（智能识别）
        source_fields = self._extract_source_fields(class_name, data_types, content)
        
        # 提取时间戳逻辑
        timestamp_logic = self._extract_timestamp_logic(tree)
        
        # 提取验证逻辑
        validation_logic = self._extract_validation_logic(content)
        
        # 确定基础解析器类型
        base_parser_type = self._determine_base_parser(class_name, data_types)
        
        # 支持的文件扩展名
        file_extensions = self._infer_extensions(data_types)

        return ScriptFeatures(
            script_name=script_name,
            data_types=data_types,
            parse_patterns=parse_patterns,
            field_extractors=field_extractors,
            timestamp_logic=timestamp_logic,
            validation_logic=validation_logic,
            class_name=class_name,
            base_parser_type=base_parser_type,
            file_extensions=file_extensions,
            source_fields=source_fields
        )
    
    def _extract_source_fields(self, class_name: str, data_types: List[str], content: str) -> List[Dict[str, str]]:
        """智能提取源字段列表"""
        fields = []
        
        # 根据解析器类型添加默认字段
        if 'IMU' in class_name or 'imu' in str(data_types).lower():
            default_fields = [
                {'source': 'cnt', 'target': 'cnt', 'type': 'integer'},
                {'source': 'ax', 'target': 'ax', 'type': 'float'},
                {'source': 'ay', 'target': 'ay', 'type': 'float'},
                {'source': 'az', 'target': 'az', 'type': 'float'},
                {'source': 'gx', 'target': 'gx', 'type': 'float'},
                {'source': 'gy', 'target': 'gy', 'type': 'float'},
                {'source': 'gz', 'target': 'gz', 'type': 'float'},
                {'source': 'timestamp', 'target': 'timestamp', 'type': 'datetime'},
            ]
            fields.extend(default_fields)
        elif 'CNAP' in class_name or 'cnap' in str(data_types).lower():
            default_fields = [
                {'source': 'cnap_type', 'target': 'cnap_type', 'type': 'string'},
                {'source': 'wave_t', 'target': 'wave_t', 'type': 'float'},
                {'source': 'pressure', 'target': 'pressure', 'type': 'float'},
                {'source': 'beat_t', 'target': 'beat_t', 'type': 'float'},
                {'source': 'Systolic_BP', 'target': 'Systolic_BP', 'type': 'float'},
                {'source': 'Diastolic_BP', 'target': 'Diastolic_BP', 'type': 'float'},
                {'source': 'Heart_Rate', 'target': 'Heart_Rate', 'type': 'float'},
                {'source': 'Mean_Arterial_Pressure', 'target': 'Mean_Arterial_Pressure', 'type': 'float'},
                {'source': 'Pulse_Pressure', 'target': 'Pulse_Pressure', 'type': 'float'},
                {'source': 'Heart_Rate_Variability', 'target': 'Heart_Rate_Variability', 'type': 'float'},
                {'source': 'Mean_Pulse_Pressure', 'target': 'Mean_Pulse_Pressure', 'type': 'float'},
                {'source': 'Stroke_Volume', 'target': 'Stroke_Volume', 'type': 'float'},
                {'source': 'Vascular_Resistance', 'target': 'Vascular_Resistance', 'type': 'float'},
                {'source': 'PPV', 'target': 'PPV', 'type': 'float'},
                {'source': 'SVV', 'target': 'SVV', 'type': 'float'},
                {'source': 'Ejection_Fraction', 'target': 'Ejection_Fraction', 'type': 'float'},
                {'source': 'timestamp', 'target': 'timestamp', 'type': 'datetime'},
            ]
            fields.extend(default_fields)
        elif 'Cardiovascular' in class_name:
            default_fields = [
                {'source': 'ecg_lead', 'target': 'ecg_lead', 'type': 'float'},
                {'source': 'heart_rate', 'target': 'heart_rate', 'type': 'float'},
                {'source': 'timestamp', 'target': 'timestamp', 'type': 'datetime'},
            ]
            fields.extend(default_fields)
        else:
            # 通用字段
            default_fields = [
                {'source': 'value', 'target': 'value', 'type': 'float'},
                {'source': 'timestamp', 'target': 'timestamp', 'type': 'datetime'},
            ]
            fields.extend(default_fields)
        
        # 从脚本内容中查找更多字段
        common_fields = ['ax', 'ay', 'az', 'gx', 'gy', 'gz', 
                         'cnt', 'count', 'seq', 'timestamp', 'time',
                         'Systolic_BP', 'Diastolic_BP', 'Heart_Rate', 'MAP',
                         'Mean_Arterial_Pressure', 'Pulse_Pressure',
                         'Heart_Rate_Variability', 'Mean_Pulse_Pressure',
                         'Stroke_Volume', 'Vascular_Resistance',
                         'PPV', 'SVV', 'Ejection_Fraction',
                         'cnap_type', 'wave_t', 'pressure', 'beat_t',
                         'wheel', 'speed', 'status']
        
        for field in common_fields:
            if field in content:
                # 检查是否已存在
                if not any(f['source'] == field for f in fields):
                    dtype = self._infer_field_type(field)
                    fields.append({
                        'source': field, 
                        'target': field, 
                        'type': dtype
                    })
        
        return fields
    
    def _infer_field_type(self, field_name: str) -> str:
        """根据字段名推断数据类型"""
        lower = field_name.lower()
        if any(kw in lower for kw in ['timestamp', 'time', 'date']):
            return 'datetime'
        if any(kw in lower for kw in ['ax', 'ay', 'az', 'gx', 'gy', 'gz', 'accel', 'gyro',
                                       'bp', 'map', 'pressure', 'pulse', 'volume',
                                       'resistance', 'ppv', 'svv', 'ejection', 'fraction',
                                       'variability', 'stroke', 'vascular', 'arterial',
                                       'systolic', 'diastolic', 'heart_rate', 'mean_']):
            return 'float'
        if any(kw in lower for kw in ['seq', 'id', 'count', 'cnt']):
            return 'integer'
        if any(kw in lower for kw in ['status', 'state', 'flag', 'crc', 'type', 'cnap_type']):
            return 'string'
        return 'float'

    def _extract_class_name(self, tree: ast.Module) -> str:
        """提取类名"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if 'Parser' in node.name or 'Analyzer' in node.name:
                    return node.name
        return 'DataParser'

    def _extract_data_types(self, content: str) -> List[str]:
        """提取数据类型关键词"""
        data_types = []
        keywords = ['IMU', 'CNAP', 'CSV', 'JSON', 'Binary', 'Sensor', 'Cardiovascular']
        
        for keyword in keywords:
            if keyword in content:
                data_types.append(keyword)
        
        if not data_types:
            data_types = ['General']
        
        return data_types

    def _extract_parse_patterns(self, content: str) -> List[str]:
        """提取解析模式"""
        patterns = []
        
        # 提取正则表达式
        pattern_matches = re.findall(r'r["\'](.+?)["\']', content)
        patterns.extend(pattern_matches[:5])
        
        # 提取字符串匹配关键词
        if 'AA' in content and 'BB' in content:
            patterns.append('AA..BB')
        
        if 'csv' in content.lower():
            patterns.append('CSV')
        
        if 'json' in content.lower():
            patterns.append('JSON')
        
        return patterns

    def _extract_field_extractors(self, tree: ast.Module) -> Dict[str, str]:
        """提取字段提取逻辑"""
        extractors = {}
        
        # 查找常见字段赋值
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        field = target.id
                        if field in ['timestamp', 'ax', 'ay', 'az', 'gx', 'gy', 'gz', 
                                     'Systolic_BP', 'Diastolic_BP', 'Heart_Rate', 
                                     'value', 'data']:
                            if isinstance(node.value, ast.Name):
                                extractors[field] = node.value.id
                            elif isinstance(node.value, ast.Call):
                                extractors[field] = 'function_call'
        
        return extractors

    def _extract_timestamp_logic(self, tree: ast.Module) -> Optional[str]:
        """提取时间戳处理逻辑"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if 'time' in target.id.lower() or 'timestamp' in target.id.lower():
                            return 'detected'
        return None

    def _extract_validation_logic(self, content: str) -> Optional[str]:
        """提取数据验证逻辑"""
        if 'validate' in content.lower() or 'check' in content.lower():
            return 'has_validation'
        return None

    def _determine_base_parser(self, class_name: str, data_types: List[str]) -> str:
        """确定基础解析器类型"""
        if 'IMU' in class_name or 'imu' in str(data_types).lower():
            return 'IMUDataParser'
        elif 'CNAP' in class_name or 'cnap' in str(data_types).lower():
            return 'CNAPDataParser'
        elif 'Cardiovascular' in class_name:
            return 'CardiovascularDataParser'
        else:
            return 'BaseDataParser'

    def _infer_extensions(self, data_types: List[str]) -> List[str]:
        """推断支持的文件扩展名"""
        extensions = ['.txt', '.csv']
        
        if 'CNAP' in data_types or 'Cardiovascular' in data_types:
            extensions = ['.txt', '.csv', '.dat']
        elif 'IMU' in data_types:
            extensions = ['.txt', '.csv', '.dat', '.bin']
        
        return extensions


class ScriptGenerator:
    """脚本生成器"""

    def __init__(self):
        self.template = self._load_template()

    def _load_template(self) -> str:
        """加载解析脚本模板"""
        return '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
{script_name} 数据解析器
自动生成的解析脚本
"""

import re
import time
import logging
from typing import Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class {class_name}:
    \"\"\"{script_name} 数据解析器\"\"\"

    def __init__(self):
        self.success_count = 0
        self.error_count = 0
        self.parsing_callback = None
        self._init_patterns()

    def _init_patterns(self):
        \"\"\"初始化解析模式\"\"\"
        {pattern_init_code}

    def set_parse_callback(self, callback):
        \"\"\"设置解析回调\"\"\"
        self.parsing_callback = callback

    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        \"\"\"解析单行数据\"\"\"
        try:
            line = line.strip()
            if not line:
                return None

            {parse_logic}

            if result:
                self.success_count += 1
                if self.parsing_callback:
                    try:
                        self.parsing_callback(result)
                    except Exception as e:
                        logger.error(f"回调执行失败: {{e}}")
                return result
            else:
                self.error_count += 1
                return None

        except Exception as e:
            self.error_count += 1
            logger.error(f"解析失败: {{e}}")
            return None

    def parse_file(self, file_path: str) -> pd.DataFrame:
        \"\"\"解析整个文件\"\"\"
        records = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    parsed_data = self.parse_line(line)
                    if parsed_data:
                        records.append(parsed_data)
        except Exception as e:
            logger.error(f"读取文件失败: {{e}}")
        
        return pd.DataFrame(records)

    def {validation_method}
        {validation_code}

    def get_stats(self) -> Dict[str, int]:
        \"\"\"获取解析统计\"\"\"
        return {{
            'success': self.success_count,
            'error': self.error_count,
            'total': self.success_count + self.error_count
        }}
'''

    def generate_script(self, features: ScriptFeatures, 
                       custom_name: Optional[str] = None) -> Tuple[str, str]:
        """根据特征生成新解析脚本

        Args:
            features: 脚本特征
            custom_name: 自定义名称

        Returns:
            (脚本内容, 类名)
        """
        script_name = custom_name or f"{features.script_name}_AutoGen"
        class_name = f"{script_name.replace(' ', '')}Parser"
        
        # 生成模式初始化代码
        pattern_init_code = self._generate_pattern_init(features)
        
        # 生成解析逻辑
        parse_logic = self._generate_parse_logic(features)
        
        # 生成验证方法
        validation_method, validation_code = self._generate_validation(features)
        
        # 渲染模板
        script_content = self.template.format(
            script_name=script_name,
            class_name=class_name,
            pattern_init_code=pattern_init_code,
            parse_logic=parse_logic,
            validation_method=validation_method,
            validation_code=validation_code
        )
        
        return script_content, class_name

    def _generate_pattern_init(self, features: ScriptFeatures) -> str:
        """生成模式初始化代码"""
        code_lines = []
        
        if features.parse_patterns:
            for i, pattern in enumerate(features.parse_patterns):
                safe_pattern = pattern.replace('"', '\\"')
                code_lines.append(f"        self.pattern_{i} = re.compile(r\"{safe_pattern}\")")
        
        if not features.parse_patterns:
            if 'CNAP' in features.data_types:
                code_lines.append("        self.cnap_pattern = re.compile(r'(?:Systolic|Diastolic|HR|MAP)')")
            elif 'IMU' in features.data_types:
                code_lines.append("        self.imu_pattern = re.compile(r'AA.*?BB')")
            else:
                code_lines.append("        self.csv_split = lambda x: x.split(',')")
        
        return '\n'.join(code_lines) if code_lines else '        pass'

    def _generate_parse_logic(self, features: ScriptFeatures) -> str:
        """生成解析逻辑代码"""
        if 'CNAP' in features.data_types:
            return '''# 解析 CNAP 数据
            result = {
                'timestamp': time.time(),
                'data': line.strip()
            }
            
            if 'Systolic' in line:
                result['Systolic_BP'] = self._extract_number(line)
            if 'Diastolic' in line:
                result['Diastolic_BP'] = self._extract_number(line)
            if 'HR' in line or 'Heart' in line:
                result['Heart_Rate'] = self._extract_number(line)
                
            return result'''
        elif 'IMU' in features.data_types:
            return '''# 解析 IMU 数据
            if 'AA' in line and 'BB' in line:
                parts = re.split(r'[,\\s]+', line.strip())
                if len(parts) >= 8:
                    result = {
                        'timestamp': time.time(),
                        'ax': self._try_float(parts[1]),
                        'ay': self._try_float(parts[2]),
                        'az': self._try_float(parts[3]),
                        'gx': self._try_float(parts[4]),
                        'gy': self._try_float(parts[5]),
                        'gz': self._try_float(parts[6])
                    }
                    return result
            return None'''
        else:
            return '''# 通用解析
            parts = line.split(',')
            if len(parts) >= 2:
                result = {
                    'timestamp': time.time(),
                    'data': line.strip(),
                    'fields': parts
                }
                return result
            return None'''

    def _generate_validation(self, features: ScriptFeatures) -> Tuple[str, str]:
        """生成验证方法"""
        if features.validation_logic:
            return ('''def validate_data(self, data: Dict[str, Any]) -> bool:
        \"\"\"验证数据合法性\"\"\"''',
                '''        return isinstance(data, dict) and len(data) > 0''')
        else:
            return ('''def validate_data(self, data: Dict[str, Any]) -> bool:
        \"\"\"验证数据合法性\"\"\"''',
                '''        return True''')

    def _try_float(self, s):
        """安全的浮点数转换"""
        try:
            return float(s)
        except:
            return 0.0

    def _extract_number(self, s):
        """提取数字"""
        numbers = re.findall(r'[-+]?\d+\.?\d*', s)
        if numbers:
            return float(numbers[0])
        return 0.0


def create_script_generator() -> ScriptGenerator:
    """创建脚本生成器实例"""
    return ScriptGenerator()


def analyze_and_generate(reference_script: str, 
                        output_dir: Optional[str] = None,
                        custom_name: Optional[str] = None) -> Tuple[str, str]:
    """分析参考脚本并生成新脚本

    Args:
        reference_script: 参考脚本路径
        output_dir: 输出目录
        custom_name: 自定义名称

    Returns:
        (输出文件路径, 类名)
    """
    # 分析脚本
    analyzer = ScriptAnalyzer()
    features = analyzer.analyze_script(reference_script)
    
    logger.info(f"分析完成: {features.script_name}")
    logger.info(f"数据类型: {features.data_types}")
    logger.info(f"解析模式: {len(features.parse_patterns)} 个")
    
    # 生成脚本
    generator = ScriptGenerator()
    script_content, class_name = generator.generate_script(features, custom_name)
    
    # 保存脚本
    if not output_dir:
        output_dir = Path(reference_script).parent
    
    output_file = Path(output_dir) / f"{features.script_name}_autogen.py"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    logger.info(f"脚本已生成: {output_file}")
    
    return str(output_file), class_name
