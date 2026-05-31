"""
SciClaw SDK — 乘用车座椅评测离线分析引擎 V1.0
================================================
专业级离线SDK，整合完整的驾驶事件检测、考核指标计算、
实验组vs对照组对比、专业图表生成和Word/PDF报告输出。

核心能力:
  - 22种驾驶行为事件自动检测
  - 15项考核指标全流程计算(SEAT/VDV/TR/HIC/SRS/FDS/S_d...)
  - 实验组vs对照组自动对比(衰减率/配对检验)
  - 专业图表(时域波形/PSD频谱/SRS冲击谱/对比雷达图)
  - Word报告(.docx) + PDF报告自动生成
  - 完全离线，零网络依赖

安装:
  pip install sciclaw-sdk-1.0.0.tar.gz

快速开始:
  from sciclaw import SciClaw
  claw = SciClaw()
  claw.load("data.csv")
  claw.analyze()              # 全量分析
  claw.report("output.docx")  # 生成Word报告

作者: SciClaw | 版本: V1.0 | 日期: 2026-05-23
"""

from .engine import SciClaw as SciClawEngine

# 顶层API别名
SciClaw = SciClawEngine
analyze = SciClawEngine.quick_analyze
quick_report = SciClawEngine.quick_report

__version__ = "1.0.0"
__all__ = ["SciClaw", "analyze", "quick_report"]
