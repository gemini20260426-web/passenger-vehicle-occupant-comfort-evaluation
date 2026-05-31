#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理模块包
包含车辆管理、司机管理、车队管理、行程管理等组件
"""

from .vehicle_management_widget import VehicleManagementWidget
from .driver_management_widget import DriverManagementWidget
from .fleet_management_widget import FleetManagementWidget
from .trip_management_widget import TripManagementWidget

__all__ = [
    'VehicleManagementWidget',
    'DriverManagementWidget', 
    'FleetManagementWidget',
    'TripManagementWidget'
]
