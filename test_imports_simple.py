#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os

print(f"Python {sys.version}")
print(f"CWD: {sys.path[0]}")

print("\nTesting traceback import...")
import traceback
print("  OK: traceback imported")

print("\nTesting logging import...")
import logging
logger = logging.getLogger("test")
print("  OK: logging imported")

print("\nTesting imu_calibration_applier import...")
try:
    from core.core.data_processing.imu_calibration_applier import (
        IMUCalibrationApplier,
        create_applier_from_source_config,
        apply_calibration_to_cache
    )
    print("  OK: imu_calibration_applier imported successfully")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

print("\nTesting data_reader_manager import...")
try:
    from modules.ui.left_control_panel.utils.data_reader_manager import (
        DataSourceReader,
        DataReaderManager
    )
    print("  OK: data_reader_manager imported successfully")
except Exception as e:
    print(f"  ERROR: {e}")
    traceback.print_exc()

print("\nAll tests complete!")
