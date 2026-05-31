import csv
import struct
from collections import defaultdict

# ===================== 官方固定协议配置 =====================
# 车机ID（严格按照你提供的定义）
VEHICLE_IDS = {
    0x100: "speed_reverse",
    0x101: "steering_angle",
    0x102: "brake_signal"
}

# IMU ID段（10路IMU）
IMU_ID_RANGE = range(0x1FFF0051, 0x1FFF0065)

# ===========================================================

def parse_vehicle_can(can_id, data):
    """严格按照你提供的协议解析车机数据"""
    result = {"type": VEHICLE_IDS[can_id], "valid": True}
    
    if can_id == 0x100:
        # 车速(0-255) + 倒挡(0/1)
        result["speed_kmh"] = data[0]
        result["reverse_gear"] = bool(data[1])
        result["description"] = f"车速:{result['speed_kmh']}km/h, 倒挡:{result['reverse_gear']}"
        
    elif can_id == 0x101:
        # 16位有符号大端 → 方向盘角度(-540~540)
        angle = struct.unpack('>h', bytes(data[:2]))[0]
        result["steering_angle_deg"] = max(min(angle, 540), -540)
        result["description"] = f"方向盘角度:{result['steering_angle_deg']}°"
        
    elif can_id == 0x102:
        # 急刹信号 + 16位无符号大端油压(0-1000)
        result["emergency_brake"] = bool(data[0])
        pressure = struct.unpack('>H', bytes(data[2:4]))[0]
        result["brake_pressure"] = max(min(pressure, 1000), 0)
        result["description"] = f"急刹:{result['emergency_brake']}, 油压:{result['brake_pressure']}"
        
    return result

def parse_dataset(file_path, output_csv="parsed_result.csv"):
    """解析CAN数据集文件"""
    parsed_data = []
    stats = defaultdict(int)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            try:
                # 解析CAN日志字段
                channel = row[3]
                timestamp = row[2]
                can_id = int(row[4], 16)
                data_len = int(row[7])
                data = [int(x, 16) for x in row[8].split()] if row[8] else []
                
                # 分类解析
                if can_id in VEHICLE_IDS:
                    parsed = parse_vehicle_can(can_id, data)
                    parsed["channel"] = channel
                    parsed["timestamp"] = timestamp
                    parsed["can_id"] = hex(can_id)
                    parsed_data.append(parsed)
                    stats[f"车机_{parsed['type']}"] += 1
                    
                elif can_id in IMU_ID_RANGE:
                    stats["IMU数据"] += 1
                    
                else:
                    stats["系统辅助帧"] += 1
                    
            except Exception:
                continue

    # 输出结果
    print("="*60)
    print("数据集解析完成（严格遵循官方协议）")
    print("="*60)
    print("数据统计：")
    for k, v in stats.items():
        print(f"  {k}: {v} 帧")
        
    print("\n车机数据解析结果：")
    for item in parsed_data:
        print(f"[{item['channel']}] {item['can_id']} | {item['description']}")

    return parsed_data

# ===================== 运行解析 =====================
if __name__ == "__main__":
    # 替换为你的数据集文件路径
    DATASET_FILE = "2026_05_08_094717_ID0001K.txt"
    result = parse_dataset(DATASET_FILE)
