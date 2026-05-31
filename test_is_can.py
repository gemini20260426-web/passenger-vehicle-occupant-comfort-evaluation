#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试 _is_can_content 方法"""

import os
import sys

# 添加核心路径
core_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    'core', 'core', 'data_processing'
))
if core_path not in sys.path:
    sys.path.insert(0, core_path)

try:
    from core.core.data_processing.parser_manager import ParserManager, reset_parser_manager, get_parser_manager
    
    reset_parser_manager()
    mgr = get_parser_manager()
    
    sample_file = os.path.join(
        os.path.dirname(__file__),
        'test_data', '验证数据', '2026_05_08_094717_ID0001.txt'
    )
    
    if os.path.exists(sample_file):
        with open(sample_file, 'r', encoding='utf-8', errors='ignore') as f:
            sample_content = ''.join(f.readlines(20))
        
        # 直接调用 _is_can_content
        is_can = ParserManager._is_can_content(sample_content)
        print("_is_can_content returned:", is_can)
        
        # 调用 smart_detect_parser
        recommended = mgr.smart_detect_parser(
            file_path=sample_file,
            data_content=sample_content
        )
        if recommended:
            print("Recommended parser:", recommended.name)

except Exception as e:
    print("ERROR:", str(e))
    import traceback
    traceback.print_exc()
