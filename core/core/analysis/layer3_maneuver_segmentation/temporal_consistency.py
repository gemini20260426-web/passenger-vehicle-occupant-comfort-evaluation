#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
时序一致性校验器
"""

import logging
from typing import Optional
from ..core_types import ManeuverEvent, DrivingState


class TemporalConsistencyValidator:
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._last_event = None
        self._event_history = []

    def validate(self, event: ManeuverEvent) -> bool:
        if event.duration < 0.03:
            return False

        if event.duration > 120.0:
            return False

        if self._last_event is not None:
            gap = event.start_time - self._last_event.end_time
            if gap < 0.03:
                return False

        self._last_event = event
        self._event_history.append(event)
        if len(self._event_history) > 100:
            self._event_history = self._event_history[-50:]

        return True

    def reset(self):
        self._last_event = None
        self._event_history.clear()
