#!/usr/bin/env python3
"""charts/style.py — 统一设计系统"""

from __future__ import annotations
import platform, logging
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from typing import Tuple

logger = logging.getLogger(__name__)

# ═══ 跨平台中文字体 ═══
def _cn_font() -> str:
    try:
        from matplotlib.font_manager import FontManager
        fm = FontManager()
        avail = {f.name for f in fm.ttflist}
        sys = platform.system()
        pref = {'Windows': ['Microsoft YaHei','SimHei'], 'Darwin': ['PingFang SC','Heiti SC'],
                'Linux': ['Noto Sans CJK SC','WenQuanYi Micro Hei']}
        for fn in pref.get(sys,[]) + ['DejaVu Sans']:
            if fn in avail: return fn
    except: pass
    return 'sans-serif'

CN = _cn_font()
plt.rcParams.update({'font.sans-serif': [CN, 'DejaVu Sans'], 'axes.unicode_minus': False})

# ═══ 设计令牌 ═══
C = {
    'bg':     '#FAFAFA',
    'exp':    '#2563EB',  # 实验组蓝
    'ctrl':   '#D97706',  # 对照组橙
    'diff':   '#059669',  # 改善绿
    'bad':    '#DC2626',  # 恶化红
    'grid':   '#E2E8F0',
    'text':   '#1E293B',
    'muted':  '#94A3B8',
    'accent': '#7C3AED',
}

# 事件颜色
EV = {
    'parked':'#94A3B8','cruising':'#059669','normal_acceleration':'#3B82F6',
    'aggressive_acceleration':'#F59E0B','normal_deceleration':'#3B82F6',
    'aggressive_deceleration':'#DC2626','emergency_braking':'#DC2626',
    'left_turn':'#8B5CF6','right_turn':'#2563EB','tight_turn':'#DC2626',
    'wide_turn':'#F59E0B','weaving':'#8B5CF6','cornering_acceleration':'#D97706',
    'skid_risk':'#DC2626','rapid_direction_change':'#EA580C',
    'lane_keeping':'#10B981','constant_speed':'#2563EB',
    'hard_accel':'#F59E0B','hard_brake':'#DC2626','aggressive_accel':'#F59E0B',
}

# 事件类型 → 中文名称映射（统一源自元数据管理）
EV_CN = {
    # ── 速度类 ──
    'constant_speed': '匀速直行', 'normal_acceleration': '正常加速',
    'normal_deceleration': '正常减速', 'cruising': '恒速行驶',
    'stopped': '停车', 'parked': '驻车',
    # ── 转向类 ──
    'lane_keeping': '车道保持', 'left_turn': '左转', 'right_turn': '右转',
    'tight_turn': '小半径转弯', 'wide_turn': '大半径转弯', 'u_turn': 'U型转弯',
    # ── 复合类 ──
    'cornering_acceleration': '弯道加速', 'cornering_deceleration': '弯道减速',
    # ── 激进类 ──
    'aggressive_acceleration': '激进加速', 'aggressive_deceleration': '激进减速',
    'emergency_braking': '急刹车',
    # ── 动态类 ──
    'weaving': '蛇形驾驶', 'rapid_direction_change': '急速变向',
    # ── IMU类 ──
    'severe_bump': '剧烈颠簸', 'skid_risk': '侧滑风险', 'rollover_risk': '侧翻风险',
    # ── 兼容别名 ──
    'lane_change': '变道', 'hard_acceleration': '急加速',
    'hard_braking': '急刹车', 'sharp_turn': '急转弯',
    'straight_cruise': '直线巡航', 'parking': '驻车',
    'hard_accel': '急加速', 'hard_brake': '急刹车', 'aggressive_accel': '激进加速',
}

# 维度颜色
DIM_C = {'瞬态-冲击':'#DC2626','稳态-舒适度':'#2563EB','动态-响应':'#059669',
         '疲劳-损伤':'#D97706','时频-分析':'#7C3AED','生物力学':'#059669','通用-基础':'#94A3B8'}

class S:
    """样式工具"""
    DPI = 150

    @staticmethod
    def screen_dpi():
        try:
            from PySide6.QtWidgets import QApplication
            a = QApplication.instance()
            if a and a.primaryScreen(): return int(a.primaryScreen().logicalDotsPerInch())
        except: pass
        return 96

    @staticmethod
    def fig(w, h):
        f = Figure(figsize=(w, h), dpi=S.screen_dpi())
        f.patch.set_facecolor(C['bg'])
        return f

    @staticmethod
    def ax(fig, *args, **kw):
        a = fig.add_subplot(*args, **kw)
        a.set_facecolor(C['bg']); a.grid(True, color=C['grid'], linewidth=0.4, alpha=0.6)
        a.spines['top'].set_visible(False); a.spines['right'].set_visible(False)
        a.spines['left'].set_color(C['muted']); a.spines['bottom'].set_color(C['muted'])
        a.tick_params(labelsize=8, colors='#64748B')
        return a

    @staticmethod
    def cn(s): return {'fontfamily': CN}

    @staticmethod
    def cnb(s): return {'fontfamily': CN, 'fontweight': 'bold'}

    @staticmethod
    def barh(ax, labels, values, colors=None, **kw):
        y = range(len(labels))
        bars = ax.barh(y, values, height=0.6, color=colors or C['exp'], alpha=0.8, edgecolor='white', **kw)
        ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8, **S.cn(8)); ax.invert_yaxis()
        ax.grid(axis='x', alpha=0.3)
        return bars
