#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评测结果 SQLite 持久化存储
基于 metadata_registry 的 Schema 定义，统一存储评测结果

特性:
- WAL模式 + 批量写入缓冲
- 元数据驱动 Schema 生成
- 支持按 session/event/indicator 多维度查询
- 支持实验组/对照组分区存储
"""

import json
import sqlite3
import os
import time
import logging
import threading
from typing import Dict, Any, List, Optional, Tuple

from .metadata_registry import get_global_registry

logger = logging.getLogger(__name__)

DEFAULT_MAX_RESULTS = 500000
DEFAULT_WRITE_BUFFER_SIZE = 1000


class EvaluationResultStore:
    """评测结果 SQLite 持久化存储"""

    def __init__(self, db_path: str = None, max_results: int = DEFAULT_MAX_RESULTS):
        self._registry = get_global_registry()
        if db_path is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))))),
                'data_output'
            )
            os.makedirs(output_dir, exist_ok=True)
            db_path = os.path.join(output_dir, f'eval_results_{int(time.time())}.db')

        self.db_path = db_path
        self.max_results = max_results
        self._lock = threading.Lock()
        self._conn = None
        self._write_buffer: List[Tuple] = []
        self._init_db()
        logger.info(f"EvaluationResultStore 已创建: {db_path} (max_results={max_results})")

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")
            conn.execute("PRAGMA temp_store=MEMORY")
            schema = self._registry.generate_result_schema()
            for stmt in schema.split(';'):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evaluation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL DEFAULT 'shock',
                    location_id TEXT NOT NULL DEFAULT '',
                    group_tag TEXT NOT NULL DEFAULT 'experimental',
                    event_label TEXT,
                    event_timestamp REAL,
                    overall_score REAL,
                    overall_grade TEXT,
                    overall_risk TEXT,
                    summary TEXT,
                    raw_payload TEXT,
                    created_at REAL NOT NULL DEFAULT (strftime('%s', 'now')),
                    UNIQUE(session_id, event_id, group_tag)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_event_session ON evaluation_events(session_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_event_type ON evaluation_events(event_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_event_timestamp ON evaluation_events(event_timestamp)"
            )
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def flush(self):
        with self._lock:
            if not self._write_buffer:
                return
            conn = self._get_conn()
            buffer = list(self._write_buffer)
            self._write_buffer.clear()
            try:
                conn.executemany("""
                    INSERT OR REPLACE INTO evaluation_results
                    (session_id, event_id, indicator_code, location, group_tag,
                     value, unit, grade, pass_status, raw_data, evaluated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, buffer)
                conn.commit()
                max_id = conn.execute(
                    "SELECT MAX(id) FROM evaluation_results"
                ).fetchone()[0]
                if max_id and max_id > self.max_results:
                    delete_threshold = max_id - self.max_results
                    conn.execute(
                        "DELETE FROM evaluation_results WHERE id < ?",
                        (delete_threshold,)
                    )
                    conn.commit()
                    conn.execute("VACUUM")
            except Exception as e:
                logger.error(f"flush 失败: {e}")

    def save_result(self, session_id: str, event_id: str, indicator_code: str,
                    location: str, value: float, unit: str = '',
                    group_tag: str = 'experimental', raw_data: Dict = None,
                    evaluated_at: float = None):
        thresholds = self._registry.metric_thresholds_4level.get(indicator_code, {})
        grade = self._registry.get_4level_grade(indicator_code, value) if thresholds else ''
        pass_threshold = self._registry.diagnosis_thresholds.get(indicator_code, {})
        pass_status = 'pass' if pass_threshold and value <= pass_threshold.get('pass', float('inf')) else 'warn'
        if evaluated_at is None:
            evaluated_at = time.time()
        raw_json = json.dumps(raw_data, ensure_ascii=False) if raw_data else None
        with self._lock:
            self._write_buffer.append((
                session_id, event_id, indicator_code, location, group_tag,
                value, unit, grade, pass_status, raw_json, evaluated_at
            ))
            if len(self._write_buffer) >= DEFAULT_WRITE_BUFFER_SIZE:
                self.flush()

    def save_event(self, session_id: str, event_id: str, event_type: str = 'shock',
                   location_id: str = '', group_tag: str = 'experimental',
                   event_label: str = '', event_timestamp: float = None,
                   overall_score: float = None, overall_grade: str = '',
                   overall_risk: str = '', summary: str = '',
                   raw_payload: Dict = None):
        payload_json = json.dumps(raw_payload, ensure_ascii=False) if raw_payload else None
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO evaluation_events
                (session_id, event_id, event_type, location_id, group_tag,
                 event_label, event_timestamp, overall_score, overall_grade,
                 overall_risk, summary, raw_payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, event_id, event_type, location_id, group_tag,
                  event_label, event_timestamp, overall_score, overall_grade,
                  overall_risk, summary, payload_json))
            conn.commit()

    def start_session(self, session_id: str, session_name: str = '',
                      data_source: str = '') -> float:
        started_at = time.time()
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                INSERT OR IGNORE INTO evaluation_sessions
                (session_id, session_name, data_source, started_at)
                VALUES (?, ?, ?, ?)
            """, (session_id, session_name, data_source, started_at))
            conn.commit()
        return started_at

    def complete_session(self, session_id: str, total_events: int = 0,
                         total_indicators: int = 0):
        completed_at = time.time()
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                UPDATE evaluation_sessions
                SET completed_at = ?, total_events = ?, total_indicators = ?
                WHERE session_id = ?
            """, (completed_at, total_events, total_indicators, session_id))
            conn.commit()

    def query_by_session(self, session_id: str, group_tag: str = None) -> List[Dict]:
        self.flush()
        conn = self._get_conn()
        if group_tag:
            rows = conn.execute(
                """SELECT * FROM evaluation_results
                   WHERE session_id = ? AND group_tag = ?
                   ORDER BY evaluated_at ASC""",
                (session_id, group_tag)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM evaluation_results
                   WHERE session_id = ?
                   ORDER BY evaluated_at ASC""",
                (session_id,)
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def query_by_event(self, session_id: str, event_id: str,
                       group_tag: str = None) -> List[Dict]:
        self.flush()
        conn = self._get_conn()
        if group_tag:
            rows = conn.execute(
                """SELECT * FROM evaluation_results
                   WHERE session_id = ? AND event_id = ? AND group_tag = ?
                   ORDER BY evaluated_at ASC""",
                (session_id, event_id, group_tag)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM evaluation_results
                   WHERE session_id = ? AND event_id = ?
                   ORDER BY evaluated_at ASC""",
                (session_id, event_id)
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def query_by_indicator(self, session_id: str, indicator_code: str,
                           group_tag: str = None) -> List[Dict]:
        self.flush()
        conn = self._get_conn()
        if group_tag:
            rows = conn.execute(
                """SELECT * FROM evaluation_results
                   WHERE session_id = ? AND indicator_code = ? AND group_tag = ?
                   ORDER BY value DESC""",
                (session_id, indicator_code, group_tag)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM evaluation_results
                   WHERE session_id = ? AND indicator_code = ?
                   ORDER BY value DESC""",
                (session_id, indicator_code)
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def query_group_comparison(self, session_id: str, indicator_code: str
                               ) -> Dict[str, List[Dict]]:
        self.flush()
        conn = self._get_conn()
        result = {'experimental': [], 'control': []}
        for group_tag in ['experimental', 'control']:
            rows = conn.execute(
                """SELECT * FROM evaluation_results
                   WHERE session_id = ? AND indicator_code = ? AND group_tag = ?
                   ORDER BY value DESC""",
                (session_id, indicator_code, group_tag)
            ).fetchall()
            result[group_tag] = [self._row_to_dict(r) for r in rows]
        return result

    def get_session_stats(self, session_id: str) -> Dict:
        self.flush()
        conn = self._get_conn()
        session = conn.execute(
            "SELECT * FROM evaluation_sessions WHERE session_id = ?",
            (session_id,)
        ).fetchone()
        if not session:
            return {}
        grade_dist = conn.execute("""
            SELECT grade, COUNT(*) as cnt
            FROM evaluation_results
            WHERE session_id = ?
            GROUP BY grade
        """, (session_id,)).fetchall()
        indicator_count = conn.execute("""
            SELECT COUNT(DISTINCT indicator_code)
            FROM evaluation_results WHERE session_id = ?
        """, (session_id,)).fetchone()[0]
        event_count = conn.execute("""
            SELECT COUNT(DISTINCT event_id)
            FROM evaluation_results WHERE session_id = ?
        """, (session_id,)).fetchone()[0]
        return {
            'session_id': session[0],
            'session_name': session[1],
            'data_source': session[2],
            'total_events': session[3] or event_count,
            'total_indicators': session[4] or indicator_count,
            'started_at': session[5],
            'completed_at': session[6],
            'grade_distribution': {r[0]: r[1] for r in grade_dist if r[0]},
        }

    @staticmethod
    def _row_to_dict(row: Tuple) -> Dict:
        columns = ['id', 'session_id', 'event_id', 'indicator_code', 'location',
                   'group_tag', 'value', 'unit', 'grade', 'pass_status',
                   'raw_data', 'evaluated_at', 'created_at']
        return dict(zip(columns, row))

    def close(self):
        self.flush()
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def __del__(self):
        self.close()