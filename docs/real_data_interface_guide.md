# 真实数据接口实现指南

## 概述
本文档说明如何实现多源异构数据同步配置中心的真实数据接口，替换所有模拟数据生成。

## 已清理的模拟数据模块

### 1. 核心同步引擎 (sync_engine.py)
- ✅ 清理了 `_simulate_source_data` 方法
- ✅ 增强了 `_collect_real_source_data` 方法
- ✅ 添加了 `_process_real_data` 方法
- ✅ 禁用了随机数据生成

### 2. 数据源接口 (data_source_interfaces.py)
- ✅ 清理了IMU数据源的模拟数据生成
- ✅ 清理了CNAP数据源的模拟数据生成  
- ✅ 清理了MQTT数据源的模拟数据生成
- ✅ 添加了真实设备接口框架

### 3. 性能监控器 (performance_monitor.py)
- ✅ 清理了所有随机性能指标生成
- ✅ 实现了真实系统监控（psutil）
- ✅ 添加了基于系统状态的估算逻辑

### 4. 数据融合模块 (data_fusion.py)
- ✅ 清理了测试代码中的随机数据生成
- ✅ 使用真实数据示例框架

### 5. UI组件
- ✅ 清理了多源同步配置面板中的模拟数据
- ✅ 清理了实时监控标签页中的模拟数据
- ✅ 实现了基于真实系统状态的性能指标

### 6. 传感器管理器
- ✅ 清理了传感器管理器中的模拟数据生成
- ✅ 添加了真实传感器数据获取框架

## 需要实现的真实数据接口

### 1. IMU设备接口
```python
def _get_real_device_data(self) -> Optional[Dict[str, Any]]:
    """从真实IMU设备获取数据"""
    try:
        # 实现串口通信
        import serial
        
        # 配置串口
        ser = serial.Serial(
            port=self.config.get('device_path', '/dev/ttyUSB0'),
            baudrate=self.config.get('baud_rate', 115200),
            timeout=1
        )
        
        # 读取数据
        if ser.in_waiting:
            data = ser.readline().decode('utf-8').strip()
            # 解析IMU数据格式
            parsed_data = self._parse_imu_data(data)
            ser.close()
            return parsed_data
        
        ser.close()
        return None
        
    except Exception as e:
        logger.error(f"获取IMU真实设备数据失败: {e}")
        return None

def _parse_imu_data(self, raw_data: str) -> Dict[str, Any]:
    """解析IMU原始数据"""
    try:
        # 根据设备协议解析数据
        # 例如：$IMU,ax,ay,az,gx,gy,gz,temp*checksum
        parts = raw_data.split(',')
        if len(parts) >= 7 and parts[0] == '$IMU':
            return {
                'accelerometer': [
                    float(parts[1]),  # ax
                    float(parts[2]),  # ay  
                    float(parts[3])   # az
                ],
                'gyroscope': [
                    float(parts[4]),  # gx
                    float(parts[5]),  # gy
                    float(parts[6])   # gz
                ],
                'temperature': float(parts[7]) if len(parts) > 7 else 25.0
            }
        return None
    except Exception as e:
        logger.error(f"解析IMU数据失败: {e}")
        return None
```

### 2. CNAP设备接口
```python
def _get_real_cnap_data(self) -> Optional[Dict[str, Any]]:
    """从真实CNAP设备获取数据"""
    try:
        # 实现串口通信
        import serial
        
        # 配置串口
        ser = serial.Serial(
            port=self.config.get('device_path', '/dev/ttyUSB1'),
            baudrate=self.config.get('baud_rate', 9600),
            timeout=1
        )
        
        # 读取数据
        if ser.in_waiting:
            data = ser.readline().decode('utf-8').strip()
            # 解析CNAP数据格式
            parsed_data = self._parse_cnap_data(data)
            ser.close()
            return parsed_data
        
        ser.close()
        return None
        
    except Exception as e:
        logger.error(f"获取CNAP真实设备数据失败: {e}")
        return None

def _parse_cnap_data(self, raw_data: str) -> Dict[str, Any]:
    """解析CNAP原始数据"""
    try:
        # 根据设备协议解析数据
        # 例如：$CNAP,systolic,diastolic,pulse_rate*checksum
        parts = raw_data.split(',')
        if len(parts) >= 4 and parts[0] == '$CNAP':
            systolic = float(parts[1])
            diastolic = float(parts[2])
            pulse_rate = float(parts[3])
            
            return {
                'systolic_pressure': systolic,
                'diastolic_pressure': diastolic,
                'mean_pressure': (systolic + 2 * diastolic) / 3,
                'pulse_rate': pulse_rate,
                'signal_quality': 0.95  # 真实数据质量
            }
        return None
    except Exception as e:
        logger.error(f"解析CNAP数据失败: {e}")
        return None
```

### 3. MQTT接口
```python
def _get_real_mqtt_data(self) -> Optional[Dict[str, Any]]:
    """从真实MQTT代理获取数据"""
    try:
        import paho.mqtt.client as mqtt
        
        # 创建MQTT客户端
        client = mqtt.Client()
        
        # 设置回调函数
        received_data = {}
        
        def on_message(client, userdata, msg):
            try:
                import json
                data = json.loads(msg.payload.decode())
                received_data.update(data)
            except Exception as e:
                logger.error(f"解析MQTT消息失败: {e}")
        
        client.on_message = on_message
        
        # 连接到代理
        client.connect(self.broker, self.port, 60)
        client.subscribe(self.topic)
        
        # 等待数据
        client.loop_start()
        time.sleep(0.1)  # 等待100ms
        client.loop_stop()
        client.disconnect()
        
        if received_data:
            return received_data
        else:
            return None
            
    except Exception as e:
        logger.error(f"获取MQTT真实数据失败: {e}")
        return None
```

### 4. 传感器接口
```python
def _get_real_sensor_data(self) -> Optional[Dict[str, Any]]:
    """从真实传感器获取数据"""
    try:
        # 实现硬件接口通信
        # 例如：I2C、SPI、GPIO等
        
        # 这里需要根据具体的硬件平台实现
        # 例如：树莓派、Arduino、STM32等
        
        logger.debug("真实传感器接口需要根据硬件平台实现")
        return None
        
    except Exception as e:
        logger.error(f"获取真实传感器数据失败: {e}")
        return None
```

## 配置说明

### 真实数据模式配置
```json
{
    "system_mode": "real_data_only",
    "disable_simulation": true,
    "force_real_data": true
}
```

### 数据源配置
```json
{
    "connection": {
        "device_path": "/dev/ttyUSB0",
        "baud_rate": 115200,
        "simulate_data": false
    }
}
```

## 注意事项

1. **硬件依赖**: 实现真实数据接口需要相应的硬件设备和驱动
2. **协议解析**: 需要了解具体设备的数据协议格式
3. **错误处理**: 真实设备可能不稳定，需要完善的错误处理机制
4. **性能优化**: 避免频繁的硬件访问，合理设置采样率
5. **数据验证**: 对真实数据进行质量检查和验证

## 测试建议

1. 使用虚拟串口工具测试串口通信
2. 使用MQTT测试代理验证消息传递
3. 使用真实传感器进行集成测试
4. 监控系统性能和资源使用情况

## 下一步

1. 根据实际硬件设备实现相应的接口
2. 完善错误处理和恢复机制
3. 优化数据采集和处理性能
4. 添加数据质量监控和告警
