#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试ZIP文件处理和二进制检测"""

import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, project_root)

print("=" * 70)
print("ZIP & Binary Detection Test")
print("=" * 70)

# 1. 测试ZIP文件读取（模拟二进制垃圾检测）
zip_file = r"d:\UI重构_全量备份_20250824_233403\徐宁数据\2026_05_07_180932_ID0001.zip"
print(f"\n1. Testing ZIP file as text (simulating wrong file selection):")
print("-" * 70)
try:
    with open(zip_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read(1000)
    null_count = content.count('\x00')
    printable = sum(1 for c in content if c.isprintable() or c in '\n\r\t')
    ratio = printable / len(content) if len(content) > 0 else 0
    print(f"   Null bytes: {null_count}")
    print(f"   Printable ratio: {ratio:.2%}")
    print(f"   Would be rejected as binary: {null_count > 10 or ratio < 0.3}")
    print(f"   Contains 'AA': {'AA' in content}")
    print(f"   Contains 'BB': {'BB' in content}")
except Exception as e:
    print(f"   Error: {e}")

# 2. 测试正常CAN文件
can_file = r"d:\UI重构_全量备份_20250824_233403\徐宁数据\2026_05_07_180932_ID0001_extracted\2026_05_07_180932_ID0001.txt"
print(f"\n2. Testing normal CAN file:")
print("-" * 70)
try:
    with open(can_file, 'r', encoding='gbk') as f:
        content = f.read(1000)
    null_count = content.count('\x00')
    printable = sum(1 for c in content if c.isprintable() or c in '\n\r\t')
    ratio = printable / len(content) if len(content) > 0 else 0
    print(f"   Null bytes: {null_count}")
    print(f"   Printable ratio: {ratio:.2%}")
    print(f"   Would pass binary check: {null_count <= 10 and ratio >= 0.3}")
except Exception as e:
    print(f"   Error: {e}")

# 3. 测试ZIP自动解压
print(f"\n3. Testing ZIP auto-extraction:")
print("-" * 70)
try:
    import zipfile
    import tempfile
    extract_dir = os.path.join(tempfile.gettempdir(), 'trae_can_extracted')
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_file, 'r') as zf:
        txt_files = [n for n in zf.namelist() if n.lower().endswith('.txt')]
        print(f"   TXT files in ZIP: {txt_files}")
        if txt_files:
            zf.extract(txt_files[0], extract_dir)
            extracted = os.path.join(extract_dir, txt_files[0])
            print(f"   Extracted to: {extracted}")
            print(f"   File exists: {os.path.exists(extracted)}")
            with open(extracted, 'r', encoding='gbk') as f:
                first_line = f.readline().strip()
            print(f"   First line: {first_line[:80]}...")
except Exception as e:
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()

# 4. 测试CAN parser parse_file
print(f"\n4. Testing CANFullParser.parse_file:")
print("-" * 70)
try:
    from core.core.data_processing.can_parser_v2 import CANFullParser
    parser = CANFullParser()
    try:
        import glob as _glob
        drive_dir = os.path.dirname(can_file)
        candidates = (
            _glob.glob(drive_dir + '/*park*') +
            _glob.glob(drive_dir + '/*Park*') +
            _glob.glob(drive_dir + '/*PARK*') +
            _glob.glob(drive_dir + '/*驻车*')
        )
        candidates = [c for c in candidates
                      if not os.path.basename(c).startswith('parsed_')]
        if candidates:
            parser.calibrate(candidates[0])
            print(f"   Using park file: {candidates[0]}")
        else:
            parser._set_default_calibration()
            print(f"   Using default calibration")
    except Exception:
        parser._set_default_calibration()
        print(f"   Using default calibration (fallback)")
    count = 0
    for record in parser.parse_file(can_file):
        count += 1
        if count == 1:
            print(f"   First record keys: {list(record.keys())}")
            print(f"   Field count: {len(record)}")
        if count <= 3:
            print(f"   Record {count}: {dict(list(record.items())[:5])}...")
    print(f"   Total records: {count}")
    print(f"   Success: {parser.success_count}, Errors: {parser.error_count}")
except Exception as e:
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)