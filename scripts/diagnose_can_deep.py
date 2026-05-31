#!/usr/bin/env python3
"""深度诊断：检查095939文件中的车辆信号数据"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collections import defaultdict
from core.core.data_processing.can_parser_v2 import parse_can_file, CH6_VEHICLE_IDS

FILE_095939 = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\2026_05_08_095939_ID0001.txt'
FILE_102511 = r'd:\UI重构_全量备份_20250824_233403\徐宁数据\开发者解析数据\2026_05_08_102511_ID0001.txt'

for label, fpath in [("095939", FILE_095939), ("102511(开发者)", FILE_102511)]:
    print(f"\n{'='*60}")
    print(f"文件: {label}")
    print(f"{'='*60}")
    
    records = parse_can_file(fpath)
    
    for cid in ['0x100', '0x101', '0x102']:
        key = (cid, 'ch6')
        if key not in records:
            print(f"  {cid}: 未找到!")
            continue
        
        recs = records[key]
        print(f"\n  {cid}: 共{len(recs)}条")
        
        if cid == '0x100':
            speeds = [r['data'][0] for r in recs if len(r['data']) > 0]
            reverses = [r['data'][1] for r in recs if len(r['data']) > 1]
            unique_speeds = sorted(set(speeds))
            print(f"    速度范围: {min(speeds)}~{max(speeds)} km/h")
            print(f"    唯一速度值({len(unique_speeds)}个): {unique_speeds[:20]}{'...' if len(unique_speeds) > 20 else ''}")
            print(f"    非零速度记录数: {sum(1 for s in speeds if s > 0)}")
            print(f"    倒挡记录数: {sum(1 for r in reverses if r == 1)}")
            print(f"    前5条: {[f'{s}km/h' for s in speeds[:5]]}")
            print(f"    后5条: {[f'{s}km/h' for s in speeds[-5:]]}")
            
        elif cid == '0x101':
            steerings = []
            for r in recs:
                if len(r['data']) >= 2:
                    v = struct.unpack('>h', r['data'][0:2])[0]
                    steerings.append(v)
            unique_steer = sorted(set(steerings))
            print(f"    方向盘范围: {min(steerings)}~{max(steerings)}")
            print(f"    唯一方向盘值({len(unique_steer)}个): {unique_steer[:20]}{'...' if len(unique_steer) > 20 else ''}")
            print(f"    前5条: {steerings[:5]}")
            print(f"    后5条: {steerings[-5:]}")
            # 显示原始hex
            print(f"    原始hex样本(前3条):")
            for i, r in enumerate(recs[:3]):
                h = ' '.join(f'{b:02x}' for b in r['data'][:4])
                print(f"      [{i}] {h} -> {steerings[i] if i < len(steerings) else '?'}")
                
        elif cid == '0x102':
            ebrakes = [r['data'][0] for r in recs if len(r['data']) > 0]
            pressures = []
            for r in recs:
                if len(r['data']) >= 4:
                    p = (r['data'][2] << 8) | r['data'][3]
                    pressures.append(p)
            print(f"    急刹触发次数: {sum(1 for e in ebrakes if e == 1)}")
            print(f"    油压范围: {min(pressures)}~{max(pressures)}")
            print(f"    非零油压记录数: {sum(1 for p in pressures if p > 0)}")

print(f"\n{'='*60}")
print("结论")
print(f"{'='*60}")