#!/usr/bin/env python3
"""振动台架实验后台分析线程"""

from PySide6.QtCore import QThread, Signal
import traceback
import logging

logger = logging.getLogger(__name__)


class ShakerAnalysisWorker(QThread):
    """后台分析线程 — 单工况或多工况批量分析

    信号:
        progress(pct, msg)      — 进度更新
        finished(results_list)  — 分析完成，返回 AnalysisResult 列表
        error(msg)              — 分析出错
    """

    progress = Signal(int, str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, filepaths: list, parent=None):
        """初始化分析线程

        Args:
            filepaths: [(filepath, condition_label), ...] 或 [filepath, ...]
        """
        super().__init__(parent)
        self._filepaths = filepaths
        self._cancel_flag = False
        self._pipeline = None

    def cancel(self):
        """请求取消分析"""
        self._cancel_flag = True
        if self._pipeline:
            self._pipeline.cancel()

    def run(self):
        try:
            from core.core.seat_evaluation.shaker_pipeline import ShakerAnalysisPipeline

            self._pipeline = ShakerAnalysisPipeline()
            self._pipeline.set_progress_callback(self._on_progress)

            results = []

            for entry in self._filepaths:
                if self._cancel_flag:
                    break

                if isinstance(entry, tuple):
                    filepath, label = entry
                else:
                    filepath = entry
                    label = ''

                result = self._pipeline.analyze_single(filepath, label)
                if result:
                    results.append(result)

            self.finished.emit(results)

        except Exception as e:
            logger.error(f"台架分析失败: {e}\n{traceback.format_exc()}")
            self.error.emit(f"{e}")

    def _on_progress(self, pct: int, msg: str):
        if not self._cancel_flag:
            self.progress.emit(pct, msg)