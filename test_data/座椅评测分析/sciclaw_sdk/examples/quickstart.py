"""
SciClaw SDK — 快速入门示例
==========================

运行: python quickstart.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sciclaw import SciClaw

# ============================================================
# 示例1: 一行代码 — 全流程分析
# ============================================================
print("=" * 60)
print("  SciClaw SDK V1.0 — 快速入门")
print("=" * 60)

# 查找测试数据
test_files = []
for root, dirs, files in os.walk("."):
    for f in files:
        if f.endswith('.csv') and 'parsed_data' in f:
            test_files.append(os.path.join(root, f))

if test_files:
    csv_path = test_files[0]
    print(f"\n测试数据: {csv_path}")

    # 一行全流程分析
    claw = SciClaw()
    claw.load(csv_path).analyze("./demo_output")
else:
    print("\n未找到测试CSV文件。请将 parsed_data CSV 放在当前目录。")
    print("\n用法示例:")
    print('  claw = SciClaw()')
    print('  claw.load("your_data.csv")')
    print('  claw.analyze("./output")')

print("\n快速API:")
print("  claw.detect_events()       # 仅事件检测")
print("  claw.compute_indicators()  # 仅指标计算")
print("  claw.compare_groups()      # 仅对照对比")
print("  claw.generate_charts()     # 仅图表")
print("  claw.report('out.docx')    # 仅报告")
