"""
SciClaw 核心引擎 — 统一入口
===========================
整合全部子系统，提供一站式分析接口。
"""

import os, sys, json, time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

# 延迟导入子模块，按需加载
def _lazy_import(module_name):
    try:
        return __import__(f'sciclaw.{module_name}', fromlist=[module_name])
    except ImportError as e:
        print(f"警告: 子模块 {module_name} 加载失败 ({e})，部分功能不可用")
        return None

@dataclass
class AnalysisResult:
    """分析结果容器"""
    info: Dict = field(default_factory=dict)        # 基本信息
    events: List = field(default_factory=list)       # 驾驶事件
    indicators: Dict = field(default_factory=dict)   # 考核指标
    comparison: Dict = field(default_factory=dict)   # 对照对比
    charts: Dict = field(default_factory=dict)       # 图表路径
    timestamp: str = ""

class SciClaw:
    """SciClaw 分析引擎 — 一行代码驱动全部分析"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._df = None
        self._data = {}
        self.result = AnalysisResult()
        self.result.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # 延迟加载子模块
        self._events_mod = None
        self._indicators_mod = None
        self._comparison_mod = None
        self._charts_mod = None
        self._report_mod = None

    def _log(self, msg: str):
        if self.verbose:
            print(f"  [SciClaw] {msg}")

    # ============================================================
    # Step 1: 数据加载
    # ============================================================

    def load(self, source) -> "SciClaw":
        """
        加载数据源。

        Args:
            source: 文件路径(str) | DataFrame | Dict

        Returns:
            self (链式调用)
        """
        self._log("加载数据...")

        if isinstance(source, str):
            if not os.path.exists(source):
                raise FileNotFoundError(f"文件不存在: {source}")
            self._df = pd.read_csv(source)
            self._source_path = source
        elif isinstance(source, pd.DataFrame):
            self._df = source
            self._source_path = None
        elif isinstance(source, dict):
            # 字典模式: {imu_name: {fields}}
            self._data = source
            self._source_path = None
            self._log(f"字典模式: {len(source)} 个IMU")
            return self
        else:
            raise TypeError(f"不支持的数据类型: {type(source)}")

        self._log(f"CSV加载: {len(self._df)} 行, "
                  f"{self._df['imu_name'].nunique()} 路IMU, "
                  f"{self._df['rel_time'].max()-self._df['rel_time'].min():.1f}s")

        # 提取基本信息
        self.result.info = self._extract_info()
        return self

    def _extract_info(self) -> Dict:
        df = self._df
        t = df['rel_time']

        info = {
            'duration_s': round(t.max() - t.min(), 2),
            'samples': len(df),
            'channels': sorted(df['channel'].unique().tolist()),
            'imus': sorted(df['imu_name'].unique().tolist()),
            'exp_imus': [n for n in df['imu_name'].unique() if n.endswith('-1')],
            'ctrl_imus': [n for n in df['imu_name'].unique() if n.endswith('-2')],
        }

        ref = df[(df['channel']=='ch1') & (df['imu_name'].str.contains('IMU1'))].sort_values('rel_time')
        if len(ref) > 0:
            info['speed_range'] = f"{ref['speed'].min():.0f}~{ref['speed'].max():.0f} km/h"
            info['wheel_range'] = f"{ref['wheel'].min():.1f}°~{ref['wheel'].max():.1f}°"

        return info

    # ============================================================
    # Step 2: 驾驶事件检测
    # ============================================================

    def detect_events(self) -> "SciClaw":
        """检测驾驶行为事件 (22种)"""
        self._log("检测驾驶事件...")

        if self._events_mod is None:
            self._events_mod = _lazy_import('events')
        if self._events_mod is None:
            return self

        # 使用CSV路径(如果有)或构建临时文件
        if hasattr(self, '_source_path') and self._source_path:
            events = self._events_mod.detect_events_from_csv(self._source_path)
        elif self._df is not None:
            events = self._events_mod.detect_events_from_df(self._df)
        else:
            self._log("无可用数据源")
            return self

        self.result.events = events
        self._log(f"检测到 {len(events)} 个事件")
        return self

    # ============================================================
    # Step 3: 考核指标计算
    # ============================================================

    def compute_indicators(self) -> "SciClaw":
        """计算全部考核指标"""
        self._log("计算考核指标...")

        if self._indicators_mod is None:
            self._indicators_mod = _lazy_import('indicators')
        if self._indicators_mod is None:
            return self

        if self._df is not None:
            self.result.indicators = self._indicators_mod.compute_all(self._df)
        else:
            self.result.indicators = self._indicators_mod.compute_all_from_dict(self._data)

        self._log(f"{len(self.result.indicators)} 项指标计算完成")
        return self

    # ============================================================
    # Step 4: 实验组vs对照组对比
    # ============================================================

    def compare_groups(self) -> "SciClaw":
        """实验组 vs 对照组自动对比"""
        self._log("实验组 vs 对照组对比...")

        if self._comparison_mod is None:
            self._comparison_mod = _lazy_import('comparison')
        if self._comparison_mod is None:
            return self

        if self._df is not None:
            self.result.comparison = self._comparison_mod.compare(self._df)
        else:
            self.result.comparison = self._comparison_mod.compare_from_dict(self._data)

        n = len(self.result.comparison)
        self._log(f"{n} 项对比完成")
        return self

    # ============================================================
    # Step 5: 专业图表生成
    # ============================================================

    def generate_charts(self, output_dir: str = "./charts") -> "SciClaw":
        """生成专业图表"""
        self._log("生成专业图表...")

        if self._charts_mod is None:
            self._charts_mod = _lazy_import('charts')
        if self._charts_mod is None:
            return self

        os.makedirs(output_dir, exist_ok=True)

        charts = {}
        if self._df is not None:
            charts = self._charts_mod.generate_all(
                self._df, self.result.events, self.result.comparison, output_dir
            )
        elif self._data:
            charts = self._charts_mod.generate_from_dict(self._data, output_dir)

        self.result.charts = charts
        self._log(f"{len(charts)} 张图表已生成")
        return self

    # ============================================================
    # Step 6: 报告生成
    # ============================================================

    def report(self, output_path: str = "analysis_report.docx",
               format: str = "docx",
               include_charts: bool = True) -> str:
        """
        生成综合分析报告。

        Args:
            output_path: 输出文件路径
            format: "docx" | "pdf" | "md"
            include_charts: 是否嵌入图表

        Returns:
            输出文件路径
        """
        self._log(f"生成报告 → {output_path}")

        if self._report_mod is None:
            self._report_mod = _lazy_import('report')
        if self._report_mod is None:
            return ""

        charts_dir = os.path.dirname(list(self.result.charts.values())[0]) \
            if self.result.charts else None

        return self._report_mod.generate(
            self.result, output_path, format, include_charts, charts_dir
        )

    # ============================================================
    # 一键全流程
    # ============================================================

    def analyze(self, output_dir: str = "./output") -> "SciClaw":
        """
        一键全流程分析: 检测 → 计算 → 对比 → 图表 → 报告

        Args:
            output_dir: 输出目录

        Returns:
            self
        """
        self._log("=" * 50)
        self._log("SciClaw 全流程分析启动")
        self._log("=" * 50)

        t0 = time.time()

        os.makedirs(output_dir, exist_ok=True)
        charts_dir = os.path.join(output_dir, "charts")

        self.detect_events()\
            .compute_indicators()\
            .compare_groups()\
            .generate_charts(charts_dir)

        # 生成报告
        report_path = os.path.join(output_dir, "综合分析报告.docx")
        self.report(report_path, "docx", True)

        # 导出JSON
        json_path = os.path.join(output_dir, "analysis_results.json")
        self._export_json(json_path)

        elapsed = time.time() - t0
        self._log(f"全流程完成 ({elapsed:.1f}s)")
        self._log(f"输出: {output_dir}/")
        self._log(f"  - 综合分析报告.docx")
        self._log(f"  - analysis_results.json")
        self._log(f"  - charts/ ({len(self.result.charts)} 张图表)")

        return self

    def _export_json(self, path: str):
        """导出结果JSON"""
        output = {
            'info': self.result.info,
            'events': [e.to_dict() if hasattr(e,'to_dict') else str(e)
                       for e in self.result.events],
            'comparison': self.result.comparison,
            'indicators_summary': {k: v for k, v in list(self.result.indicators.items())[:50]},
            'timestamp': self.result.timestamp,
        }

        # 清理numpy类型
        def convert(obj):
            if isinstance(obj, (np.integer,)): return int(obj)
            if isinstance(obj, (np.floating,)): return float(obj)
            if isinstance(obj, np.ndarray): return obj.tolist()
            return obj

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=convert)

    # ============================================================
    # 静态快捷方法
    # ============================================================

    @staticmethod
    def quick_analyze(data_source, output_dir: str = "./output") -> str:
        """一行代码完成全流程"""
        claw = SciClaw()
        claw.load(data_source).analyze(output_dir)
        return os.path.join(output_dir, "综合分析报告.docx")

    @staticmethod
    def quick_report(data_source, output: str = "report.docx") -> str:
        """一行代码生成报告"""
        claw = SciClaw(verbose=False)
        claw.load(data_source)\
            .detect_events()\
            .compute_indicators()\
            .compare_groups()\
            .generate_charts()
        return claw.report(output)
