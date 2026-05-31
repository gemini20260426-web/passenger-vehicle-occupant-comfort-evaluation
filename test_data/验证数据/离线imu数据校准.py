import csv
import struct
import json
import os
from collections import deque, defaultdict

# ===================== 核心配置（严格匹配你的设备） =====================
# 10个IMU 安装位置 + CAN ID 映射（关键！）
IMU_CONFIG = [
    {"name": "头部眉心-左", "acc_id": 0x1FFF0051, "gyro_id": 0x1FFF0052},   # IMU1
    {"name": "头部眉心-右", "acc_id": 0x1FFF0053, "gyro_id": 0x1FFF0054},   # IMU2
    {"name": "T8脊柱-左", "acc_id": 0x1FFF0055, "gyro_id": 0x1FFF0056},     # IMU3
    {"name": "T8脊柱-右", "acc_id": 0x1FFF0057, "gyro_id": 0x1FFF0058},     # IMU4
    {"name": "座椅R点-左", "acc_id": 0x1FFF0059, "gyro_id": 0x1FFF005A},   # IMU5
    {"name": "座椅R点-右", "acc_id": 0x1FFF005B, "gyro_id": 0x1FFF005C},   # IMU6
    {"name": "座椅下方-左", "acc_id": 0x1FFF005D, "gyro_id": 0x1FFF005E},   # IMU7
    {"name": "座椅下方-右", "acc_id": 0x1FFF005F, "gyro_id": 0x1FFF0060},   # IMU8
    {"name": "胸骨剑突-左", "acc_id": 0x1FFF0061, "gyro_id": 0x1FFF0062},   # IMU9
    {"name": "胸骨剑突-右", "acc_id": 0x1FFF0063, "gyro_id": 0x1FFF0064},   # IMU10
]

# 车机协议（你提供的官方标准）
VEHICLE_IDS = {
    0x100: "speed_reverse",   # 车速+倒挡
    0x101: "steering_angle",  # 方向盘
    0x102: "brake_signal"     # 急刹+油压
}

# 原厂传感器缩放因子
ACC_SCALE = 9.8 / 4096.0     # 加速度 m/s²
GYRO_SCALE = 0.07 # 角速度 deg/s
GRAVITY = 9.80665
CONFIG_FILE = "imu_calib_result.json"
# ======================================================================

class OfflineIMUCalibrator:
    def __init__(self, dataset_path):
        self.dataset_path = dataset_path
        self.imu_list = IMU_CONFIG
        self.raw_data = defaultdict(deque)
        self.calib_results = {}
        self.all_parsed_frames = []

    def load_dataset(self):
        """加载离线CAN数据集"""
        print(f"📂 加载数据集：{self.dataset_path}")
        try:
            with open(self.dataset_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 9:
                        continue
                    try:
                        can_id = int(row[4], 16)
                        data = [int(x, 16) for x in row[8].split()] if row[8] else []
                        timestamp = row[2]
                        channel = row[3]

                        # 存储IMU原始数据
                        for imu in self.imu_list:
                            if can_id == imu['acc_id'] and len(data) == 8:
                                self.raw_data[f"{imu['name']}_acc"].append(data)
                            if can_id == imu['gyro_id'] and len(data) == 8:
                                self.raw_data[f"{imu['name']}_gyro"].append(data)

                        # 存储全量帧（用于后续解析）
                        self.all_parsed_frames.append({
                            "timestamp": timestamp, "channel": channel,
                            "can_id": can_id, "data": data
                        })
                    except:
                        continue
            print(f"✅ 数据集加载完成，共 {len(self.all_parsed_frames)} 帧")
            return True
        except Exception as e:
            print(f"❌ 加载失败：{e}")
            return False

    def calibrate_single_sensor(self, data_list, sensor_type):
        """静态校准单个传感器（加速度/陀螺仪）"""
        best = {"byte_order": "<", "x_bias":0, "y_bias":0, "z_bias":0, "z_sign":1}
        scale = ACC_SCALE if sensor_type == "acc" else GYRO_SCALE

        # 计算静态零偏（静止状态平均值）
        x_vals, y_vals, z_vals = [], [], []
        for d in data_list:
            x = struct.unpack('<h', bytes(d[0:2]))[0] * scale
            y = struct.unpack('<h', bytes(d[2:4]))[0] * scale
            z = struct.unpack('<h', bytes(d[4:6]))[0] * scale
            x_vals.append(x)
            y_vals.append(y)
            z_vals.append(z)

        best["x_bias"] = sum(x_vals)/len(x_vals)
        best["y_bias"] = sum(y_vals)/len(y_vals)
        best["z_bias"] = sum(z_vals)/len(z_vals)

        # 加速度Z轴方向校正
        if sensor_type == "acc":
            best["z_sign"] = 1 if abs(best["z_bias"]) > 5 else -1
            best["scale"] = ACC_SCALE
        else:
            best["scale"] = GYRO_SCALE
            best["z_sign"] = 1
        return best

    def run_calibration(self):
        """执行全自动离线校准"""
        print("\n" + "="*80)
        print("开始 10路IMU 全自动静态校准（未校准原始数据 → 精准物理数据）")
        print("="*80)

        # 逐个校准所有IMU
        for imu in self.imu_list:
            name = imu['name']
            print(f"\n🔧 校准：{name}")

            # 校准加速度计
            acc_data = self.raw_data[f"{name}_acc"]
            acc_params = self.calibrate_single_sensor(acc_data, "acc")

            # 校准陀螺仪
            gyro_data = self.raw_data[f"{name}_gyro"]
            gyro_params = self.calibrate_single_sensor(gyro_data, "gyro")

            self.calib_results[name] = {"acc": acc_params, "gyro": gyro_params}
            print(f"  ✅ 校准完成 | 零偏已自动计算")

        # 保存校准配置
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.calib_results, f, indent=4, ensure_ascii=False)
        print(f"\n💾 校准配置已保存：{CONFIG_FILE}")
        return self.calib_results

    def parse_calibrated_data(self):
        """使用校准参数解析全量数据"""
        print("\n" + "="*80)
        print("使用校准参数解析全量数据集（输出物理单位）")
        print("="*80)

        # 车机数据（静止状态）
        vehicle_result = {"speed": 0, "reverse": 0, "steering": 0, "brake": 0, "pressure": 0}
        result_data = defaultdict(list)

        # 解析每一帧
        for frame in self.all_parsed_frames:
            can_id = frame["can_id"]
            data = frame["data"]
            ts = frame["timestamp"]

            # 解析IMU校准后数据
            for imu in self.imu_list:
                name = imu['name']
                calib = self.calib_results[name]

                # 加速度
                if can_id == imu['acc_id'] and len(data) == 8:
                    x = struct.unpack('<h', bytes(data[0:2]))[0] * calib['acc']['scale'] - calib['acc']['x_bias']
                    y = struct.unpack('<h', bytes(data[2:4]))[0] * calib['acc']['scale'] - calib['acc']['y_bias']
                    z = (struct.unpack('<h', bytes(data[4:6]))[0] * calib['acc']['scale'] - calib['acc']['z_bias']) * calib['acc']['z_sign']
                    result_data[name].append({"time": ts, "acc": [x,y,z], "gyro": [0,0,0]})

                # 陀螺仪
                if can_id == imu['gyro_id'] and len(data) == 8:
                    x = struct.unpack('<h', bytes(data[0:2]))[0] * calib['gyro']['scale'] - calib['gyro']['x_bias']
                    y = struct.unpack('<h', bytes(data[2:4]))[0] * calib['gyro']['scale'] - calib['gyro']['y_bias']
                    z = (struct.unpack('<h', bytes(data[4:6]))[0] * calib['gyro']['scale'] - calib['gyro']['z_bias']) * calib['gyro']['z_sign']
                    if result_data[name]:
                        result_data[name][-1]["gyro"] = [x,y,z]

        # 输出结果
        print("\n📊 校准后数据（静态平均值）：")
        for name, data in result_data.items():
            if not data:
                continue
            acc_x = sum([d["acc"][0] for d in data])/len(data)
            acc_y = sum([d["acc"][1] for d in data])/len(data)
            acc_z = sum([d["acc"][2] for d in data])/len(data)
            gyro_x = sum([d["gyro"][0] for d in data])/len(data)
            gyro_y = sum([d["gyro"][1] for d in data])/len(data)
            gyro_z = sum([d["gyro"][2] for d in data])/len(data)
            print(f"【{name}】")
            print(f"  加速度: X={acc_x:.3f} Y={acc_y:.3f} Z={acc_z:.3f} m/s²")
            print(f"  角速度: X={gyro_x:.3f} Y={gyro_y:.3f} Z={gyro_z:.3f} deg/s\n")

        # 保存全量解析结果
        with open("calibrated_imu_data.json", 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        print("💾 全量校准后数据已保存：calibrated_imu_data.json")

# ===================== 运行主程序 =====================
if __name__ == "__main__":
    # 替换为你的数据集文件名
    DATASET_FILE = "2026_05_08_094717_ID0001K.txt"
    
    # 1. 创建校准器
    calibrator = OfflineIMUCalibrator(DATASET_FILE)
    
    # 2. 加载数据集
    if not calibrator.load_dataset():
        exit()
    
    # 3. 全自动校准（解决未校准问题）
    calibrator.run_calibration()
    
    # 4. 解析并输出校准后数据
    calibrator.parse_calibrated_data()
    
    print("\n🎉 全部完成！10个IMU已完成校准，原始无意义数据 → 精准物理数据")
