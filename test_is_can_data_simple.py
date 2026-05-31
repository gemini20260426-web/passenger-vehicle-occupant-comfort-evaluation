#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test _is_can_data function (simple)"""

import os

def test_is_can_data(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = []
            for _ in range(20):
                line = f.readline()
                if line:
                    lines.append(line.strip())

        can_score = 0
        for line in lines:
            if '0x1FFF' in line:
                can_score += 3
            if '0x1702' in line or '0x51000' in line:
                can_score += 2
            if any(f'ch{i}' in line.lower() for i in range(1, 7)):
                can_score += 2
            if ',' in line and line.count(',') >= 8:
                parts = line.split(',')
                if len(parts) >= 10:
                    last_col = parts[-1].strip()
                    if any(c in last_col for c in 'x|ABCDEFabcdef'):
                        can_score += 1
        
        print("Final can_score:", can_score)
        print("Return:", can_score >= 4)
        return can_score >= 4
    except Exception as e:
        print("Error:", str(e))
        import traceback
        traceback.print_exc()
        return False

sample_file = os.path.join(
    os.path.dirname(__file__),
    'test_data', '验证数据', '2026_05_08_094717_ID0001.txt'
)

if os.path.exists(sample_file):
    result = test_is_can_data(sample_file)
