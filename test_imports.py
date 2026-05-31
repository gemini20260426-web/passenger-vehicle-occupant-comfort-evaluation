#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
print(f"Python {sys.version}")
print(f"CWD: {sys.path[0]}")

try:
    import traceback
    print("\n✅ traceback 已导入")
except Exception as e:
    print(f"\n❌ traceback 导入失败: {e}")

try:
    import logging
    logger = logging.getLogger("test")
    print("✅ logging 已导入")
except Exception as e:
    print(f"❌ logging 导入失败: {e}")

try:
    from core.core.data_processing.imu_calibration_applier import IMUCalibrationApplier
    print("\n✅ imu_calibration_applier 导入成功")
except Exception as e:
    print(f"\n❌ imu_calibration_applier 导入失败: {e}")
    import traceback
    traceback.print_exc()

try:
    from modules.ui.left_control_panel.utils.data_reader_manager import DataSourceReader
    print("\n✅ data_reader_manager 导入成功")
except Exception as e:
    print(f"\n❌ data_reader_manager 导入失败: {e}")
    import traceback
    traceback.print_exc()

print("\n✅ 所有测试完成")
