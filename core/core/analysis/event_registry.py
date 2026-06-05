"""
25种驾驶事件全量注册表

基于专家评测报告 COMPREHENSIVE_EVALUATION_REPORT.md 第三部分 4.1 节。
从 core_types.py 的 BEHAVIOR_TAXONOMY 和 BEHAVIOR_LABELS_CN 扩展为全量25种事件。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class EventCategory(Enum):
    """事件类别"""
    LONGITUDINAL = "longitudinal"   # 纵向
    LATERAL = "lateral"             # 侧向
    COMPOSITE = "composite"         # 复合
    ANOMALY = "anomaly"             # 异常
    STATE = "state"                 # 驾驶状态


class EventPriority(Enum):
    """事件优先级"""
    P0 = "P0"  # 紧急 (延迟<20ms, 置信度>98%)
    P1 = "P1"  # 重要 (延迟<50ms, 置信度>92%)
    P2 = "P2"  # 普通 (延迟<100ms, 置信度>90%)
    P3 = "P3"  # 低 (延迟<500ms, 置信度>85%)


@dataclass
class EventDef:
    """事件定义"""
    event_type: str
    name_cn: str
    category: EventCategory
    priority: EventPriority
    target_latency_ms: float
    target_confidence: float
    primary_signals: List[str]
    description: str = ""


# ── 25种事件全量注册表 ──
METADATA_EVENT_REGISTRY: Dict[str, EventDef] = {
    # ═══════════════════════════════════════════════════════════
    # 纵向事件 (8种)
    # ═══════════════════════════════════════════════════════════
    "emergency_braking": EventDef(
        "emergency_braking", "急刹车",
        EventCategory.LONGITUDINAL, EventPriority.P0,
        20.0, 0.98, ["speed", "Ax", "speed_d", "jerk_x"],
        "速度骤降>20km/h, 减速度<-5 m/s², 0.3-2s持续时间"
    ),
    "aggressive_deceleration": EventDef(
        "aggressive_deceleration", "激进减速",
        EventCategory.LONGITUDINAL, EventPriority.P0,
        20.0, 0.95, ["speed", "Ax", "speed_d"],
        "速度降幅5-15km/h, 减速度-5~-2.5 m/s², 0.5-4s"
    ),
    "normal_deceleration": EventDef(
        "normal_deceleration", "正常减速",
        EventCategory.LONGITUDINAL, EventPriority.P1,
        50.0, 0.90, ["speed", "Ax"],
        "速度降幅2-8km/h, 减速度-2.5~-0.5 m/s², 1-10s"
    ),
    "aggressive_acceleration": EventDef(
        "aggressive_acceleration", "激进加速",
        EventCategory.LONGITUDINAL, EventPriority.P0,
        20.0, 0.95, ["speed", "Ax", "jerk_x"],
        "速度增幅>5km/h, 加速度>2.5 m/s², 0.3-3s"
    ),
    "normal_acceleration": EventDef(
        "normal_acceleration", "正常加速",
        EventCategory.LONGITUDINAL, EventPriority.P1,
        50.0, 0.90, ["speed", "Ax"],
        "速度增幅2-8km/h, 加速度0.5-2.5 m/s², 1-15s"
    ),
    "launch": EventDef(
        "launch", "起步",
        EventCategory.LONGITUDINAL, EventPriority.P1,
        50.0, 0.90, ["speed", "Ax"],
        "从低速(<3km/h)起步, 速度增幅3-15km/h, 1-5s"
    ),
    "constant_speed": EventDef(
        "constant_speed", "匀速直行",
        EventCategory.LONGITUDINAL, EventPriority.P2,
        100.0, 0.90, ["speed", "Ax"],
        "速度波动<2km/h, 加速度波动<0.5 m/s², 持续>3s"
    ),
    "stopped": EventDef(
        "stopped", "停车",
        EventCategory.LONGITUDINAL, EventPriority.P2,
        100.0, 0.95, ["speed"],
        "速度<0.5km/h, 持续>1s"
    ),

    # ═══════════════════════════════════════════════════════════
    # 侧向事件 (8种)
    # ═══════════════════════════════════════════════════════════
    "weaving": EventDef(
        "weaving", "蛇形驾驶",
        EventCategory.LATERAL, EventPriority.P0,
        30.0, 0.95, ["wheel", "Ay", "wheel_d"],
        "方向盘摆幅>40°, Ay>3 m/s², 至少4次过零, 2-30s"
    ),
    "lane_change": EventDef(
        "lane_change", "变道",
        EventCategory.LATERAL, EventPriority.P0,
        30.0, 0.95, ["wheel", "Ay"],
        "方向盘15-60°, Ay 1.5-4 m/s², 方向单调性>70%, 0.5-5s"
    ),
    "rapid_direction_change": EventDef(
        "rapid_direction_change", "急速变向",
        EventCategory.LATERAL, EventPriority.P0,
        20.0, 0.95, ["wheel", "Ay", "wheel_d"],
        "方向盘>60°, 角速度>200°/s, Ay>4 m/s², 0.2-2s"
    ),
    "tight_turn": EventDef(
        "tight_turn", "小半径转弯",
        EventCategory.LATERAL, EventPriority.P1,
        50.0, 0.92, ["wheel", "Ay", "speed"],
        "持续转角>80°, Ay>2 m/s², 转角稳定, 1-10s"
    ),
    "wide_turn": EventDef(
        "wide_turn", "大半径转弯",
        EventCategory.LATERAL, EventPriority.P1,
        50.0, 0.92, ["wheel", "Ay", "speed"],
        "转角30-120°, Ay 1-3 m/s², 车速20-80km/h, 2-20s"
    ),
    "u_turn": EventDef(
        "u_turn", "U型转弯",
        EventCategory.LATERAL, EventPriority.P1,
        50.0, 0.92, ["wheel", "Ay", "speed"],
        "累计转角>150°, Ay>1.5 m/s², 3-20s"
    ),
    "straight_driving": EventDef(
        "straight_driving", "直线行驶",
        EventCategory.LATERAL, EventPriority.P2,
        100.0, 0.95, ["wheel", "Ay"],
        "方向盘变化<5°, Ay<0.5 m/s², 持续>3s"
    ),
    "lane_keeping": EventDef(
        "lane_keeping", "车道保持",
        EventCategory.LATERAL, EventPriority.P2,
        100.0, 0.90, ["wheel", "Ay"],
        "方向盘变化<15°, Ay<1 m/s², 持续>5s"
    ),

    # ═══════════════════════════════════════════════════════════
    # 复合事件 (3种)
    # ═══════════════════════════════════════════════════════════
    "cornering_acceleration": EventDef(
        "cornering_acceleration", "弯道加速",
        EventCategory.COMPOSITE, EventPriority.P1,
        50.0, 0.92, ["wheel", "speed", "Ax", "Ay"],
        "转弯(|wheel|>15°) + 加速(speed_d>3km/h), 1-5s"
    ),
    "cornering_deceleration": EventDef(
        "cornering_deceleration", "弯道减速",
        EventCategory.COMPOSITE, EventPriority.P1,
        50.0, 0.92, ["wheel", "speed", "Ax", "Ay"],
        "转弯(|wheel|>15°) + 减速(speed_d -8~-2km/h), 1-8s"
    ),
    "cornering_braking": EventDef(
        "cornering_braking", "弯道制动",
        EventCategory.COMPOSITE, EventPriority.P0,
        30.0, 0.95, ["wheel", "speed", "Ax", "Ay"],
        "转弯(|wheel|>15°) + 制动(speed_d<-10km/h, Ax<-2 m/s²), 0.5-3s"
    ),

    # ═══════════════════════════════════════════════════════════
    # 异常事件 (4种)
    # ═══════════════════════════════════════════════════════════
    "severe_bump": EventDef(
        "severe_bump", "剧烈颠簸",
        EventCategory.ANOMALY, EventPriority.P0,
        10.0, 0.98, ["Az", "Az_jerk"],
        "Az>5 m/s², 冲击持续时间0.01-0.3s, 极高jerk"
    ),
    "skid_risk": EventDef(
        "skid_risk", "侧滑风险",
        EventCategory.ANOMALY, EventPriority.P0,
        20.0, 0.95, ["Ay", "wheel"],
        "Ay>4 m/s², 方向盘与Ay不一致(侧滑特征)"
    ),
    "rollover_risk": EventDef(
        "rollover_risk", "侧翻风险",
        EventCategory.ANOMALY, EventPriority.P0,
        20.0, 0.95, ["Ay", "wheel"],
        "Ay>6 m/s², 估算侧倾角>15°, 持续时间>0.2s"
    ),
    "sensor_fault": EventDef(
        "sensor_fault", "传感器异常",
        EventCategory.ANOMALY, EventPriority.P0,
        10.0, 0.98, ["signal_quality"],
        "信号卡滞/超出5σ/掉线>0.05s"
    ),

    # ═══════════════════════════════════════════════════════════
    # 驾驶状态 (2种, 含6子状态)
    # ═══════════════════════════════════════════════════════════
    "normal": EventDef(
        "normal", "正常驾驶",
        EventCategory.STATE, EventPriority.P2,
        200.0, 0.95, ["speed", "wheel", "Ax", "Ay"],
        "默认回退状态, 无特殊事件时标记为normal"
    ),
    "overspeeding": EventDef(
        "overspeeding", "超速",
        EventCategory.STATE, EventPriority.P2,
        100.0, 0.90, ["speed"],
        "速度超过限速阈值(默认120km/h)"
    ),
    "cruising": EventDef(
        "cruising", "巡航",
        EventCategory.STATE, EventPriority.P3,
        500.0, 0.85, ["speed", "Ax"],
        "速度30-120km/h, 速度波动<5km/h, Ax<0.5 m/s², 持续>5s"
    ),
    "parked": EventDef(
        "parked", "驻车",
        EventCategory.STATE, EventPriority.P3,
        500.0, 0.95, ["speed"],
        "速度<0.3km/h, 持续>3s"
    ),
    "left_turn": EventDef(
        "left_turn", "左转",
        EventCategory.STATE, EventPriority.P3,
        500.0, 0.85, ["wheel", "speed"],
        "方向盘-200~-15°, 车速5-60km/h, 持续>1s"
    ),
    "right_turn": EventDef(
        "right_turn", "右转",
        EventCategory.STATE, EventPriority.P3,
        500.0, 0.85, ["wheel", "speed"],
        "方向盘15-200°, 车速5-60km/h, 持续>1s"
    ),
    "straight_cruise": EventDef(
        "straight_cruise", "直行巡航",
        EventCategory.STATE, EventPriority.P3,
        500.0, 0.85, ["speed", "wheel", "Ax"],
        "方向盘<5°, 速度30-120km/h, 速度波动<3km/h, 持续>5s"
    ),
}


# ── 辅助函数 ──

def get_event_by_category(category: EventCategory) -> Dict[str, EventDef]:
    """获取指定类别的事件"""
    return {
        k: v for k, v in METADATA_EVENT_REGISTRY.items()
        if v.category == category
    }


def get_event_by_priority(min_priority: EventPriority) -> Dict[str, EventDef]:
    """获取指定优先级及以上的事件"""
    priority_order = {EventPriority.P0: 0, EventPriority.P1: 1,
                      EventPriority.P2: 2, EventPriority.P3: 3}
    min_level = priority_order[min_priority]
    return {
        k: v for k, v in METADATA_EVENT_REGISTRY.items()
        if priority_order.get(v.priority, 99) <= min_level
    }


def get_event_names_cn() -> Dict[str, str]:
    """获取事件类型 → 中文名映射"""
    return {k: v.name_cn for k, v in METADATA_EVENT_REGISTRY.items()}


def get_event_count() -> int:
    """获取注册事件总数"""
    return len(METADATA_EVENT_REGISTRY)


def validate_event_type(event_type: str) -> bool:
    """验证事件类型是否已注册"""
    return event_type in METADATA_EVENT_REGISTRY