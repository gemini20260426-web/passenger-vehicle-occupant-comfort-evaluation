"""
主动控制座椅悬架项目 — 数据源预设模板

为数据源配置向导提供项目特定的 IMU 通道映射、信号字段映射和自动分组规则。
基于专家评测报告 COMPREHENSIVE_EVALUATION_REPORT.md 第四部分 4.2 节。
"""

# ── 项目预设配置 ──
DATA_SOURCE_PRESET = {
    "project": "active_seat_suspension",
    "display_name": "主动控制座椅悬架",
    "description": "多自由度多轴主动控制座椅悬架乘员舒适性评测系统",
    "can_channel": "ch1",
    "fs": 1000,
    "grouping_rule": "奇数=实验组(主动) / 偶数=对照组(被动)",

    # IMU 通道映射: 10路IMU，实验组(奇数) vs 对照组(偶数)
    "imu_mapping": {
        "IMU1_头部眉心-1":   {"group": "experimental", "body": "head",        "label": "头部眉心-1"},
        "IMU2_头部眉心-2":   {"group": "control",      "body": "head",        "label": "头部眉心-2"},
        "IMU3_躯干T8-1":    {"group": "experimental", "body": "torso",       "label": "躯干T8-1"},
        "IMU4_躯干T8-2":    {"group": "control",      "body": "torso",       "label": "躯干T8-2"},
        "IMU5_座垫R点-1":   {"group": "experimental", "body": "seat_r",      "label": "座垫R点-1"},
        "IMU6_座垫R点-2":   {"group": "control",      "body": "seat_r",      "label": "座垫R点-2"},
        "IMU7_座椅底部-1":  {"group": "experimental", "body": "seat_bottom", "label": "座椅底部-1"},
        "IMU8_座椅底部-2":  {"group": "control",      "body": "seat_bottom", "label": "座椅底部-2"},
        "IMU9_胸骨剑突-1":  {"group": "experimental", "body": "sternum",     "label": "胸骨剑突-1"},
        "IMU10_胸骨剑突-2": {"group": "control",      "body": "sternum",     "label": "胸骨剑突-2"},
    },

    # 实验组 IMU 列表 (奇数编号)
    "experimental_group": [
        "IMU1_头部眉心-1", "IMU3_躯干T8-1", "IMU5_座垫R点-1",
        "IMU7_座椅底部-1", "IMU9_胸骨剑突-1",
    ],

    # 对照组 IMU 列表 (偶数编号)
    "control_group": [
        "IMU2_头部眉心-2", "IMU4_躯干T8-2", "IMU6_座垫R点-2",
        "IMU8_座椅底部-2", "IMU10_胸骨剑突-2",
    ],

    # 信号字段映射: CSV列名 → 内部字段名
    "signal_mapping": {
        "Ax_m_s2": "ax",
        "Ay_m_s2": "ay",
        "Az_m_s2": "az",
        "Gx_dps":  "gx",
        "Gy_dps":  "gy",
        "Gz_dps":  "gz",
        "speed":   "speed",
        "wheel":   "wheel",
    },

    # 驾驶事件类型映射 (25种事件 → 评测指标)
    "event_to_evaluation_map": {
        # 纵向事件
        "emergency_braking":        ["HIC15", "ACC-H-PEAK", "JERK-H", "SRS", "RFC", "FDS"],
        "aggressive_deceleration":  ["JERK-H", "SRS", "RFC"],
        "normal_deceleration":      ["RMS", "VDV", "Cf"],
        "aggressive_acceleration":  ["JERK-H", "ACC-H-PEAK"],
        "normal_acceleration":      ["RMS", "VDV"],
        "launch":                   ["JERK-H", "RMS"],
        "constant_speed":           ["SEAT", "VDV", "TR", "AW", "OVTV", "R-FACTOR"],
        "stopped":                  [],
        # 侧向事件
        "weaving":                  ["DISP-TR", "STFT-FC", "STFT-KT"],
        "lane_change":              ["DISP-TR", "STFT-FC"],
        "rapid_direction_change":   ["DISP-TR", "STFT-KT"],
        "tight_turn":               ["DISP-TR", "RMS"],
        "wide_turn":                ["DISP-TR", "RMS"],
        "u_turn":                   ["DISP-TR", "RMS"],
        "straight_driving":         ["SEAT", "VDV", "TR"],
        "lane_keeping":             ["SEAT", "VDV"],
        # 复合事件
        "cornering_acceleration":   ["DISP-TR", "STFT-FC", "RMS"],
        "cornering_deceleration":   ["DISP-TR", "STFT-FC", "SRS"],
        "cornering_braking":        ["DISP-TR", "SRS", "RFC", "FDS"],
        # 异常事件
        "severe_bump":              ["SRS", "OVTV"],
        "skid_risk":                ["DISP-TR", "STFT-KT"],
        "rollover_risk":            ["DISP-TR"],
        "sensor_fault":             [],
        # 驾驶状态
        "normal":                   [],
        "overspeeding":             [],
        "cruising":                 ["SEAT", "VDV", "TR"],
        "parked":                   [],
        "left_turn":                ["DISP-TR", "RMS"],
        "right_turn":               ["DISP-TR", "RMS"],
        "straight_cruise":          ["SEAT", "VDV", "TR"],
    },
}

# ── 辅助函数 ──

def get_imu_group(imu_name: str) -> str:
    """获取 IMU 所属分组 (experimental/control/unknown)"""
    mapping = DATA_SOURCE_PRESET["imu_mapping"]
    if imu_name in mapping:
        return mapping[imu_name]["group"]
    # 回退: 按编号奇偶判断
    import re
    match = re.search(r'IMU(\d+)', imu_name)
    if match:
        num = int(match.group(1))
        return "experimental" if num % 2 == 1 else "control"
    return "unknown"


def get_imu_body_part(imu_name: str) -> str:
    """获取 IMU 对应的身体部位"""
    mapping = DATA_SOURCE_PRESET["imu_mapping"]
    if imu_name in mapping:
        return mapping[imu_name]["body"]
    return "unknown"


def get_experimental_imus() -> list:
    """获取所有实验组 IMU"""
    return DATA_SOURCE_PRESET["experimental_group"]


def get_control_imus() -> list:
    """获取所有对照组 IMU"""
    return DATA_SOURCE_PRESET["control_group"]


def get_signal_field(source_field: str) -> str:
    """将 CSV 列名映射为内部字段名"""
    return DATA_SOURCE_PRESET["signal_mapping"].get(source_field, source_field)


def get_evaluation_metrics_for_event(event_type: str) -> list:
    """获取事件类型对应的评测指标"""
    return DATA_SOURCE_PRESET["event_to_evaluation_map"].get(event_type, [])