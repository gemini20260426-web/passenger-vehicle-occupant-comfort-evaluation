#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析结果缓存模块 — 存储完整的 FrameResult
用于加速回放，避免重新走分析管道
"""

import json
import sqlite3
import os
import time
import logging
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import asdict
from .core_types import FrameResult, FrameFeatures, ManeuverEvent, RiskReport, DrivingState, RiskLevel, BehaviorCategory, SignalQuality

logger = logging.getLogger(__name__)


class AnalysisResultCache:
    """分析结果 SQLite 缓存 — 存储完整的 FrameResult"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__))))),
                'data_output'
            )
            os.makedirs(output_dir, exist_ok=True)
            
            # 查找已有的分析缓存文件，优先复用最近修改的（防止残留旧事件）
            import glob
            cache_files = glob.glob(os.path.join(output_dir, 'analysis_results_*.db'))
            if cache_files:
                best_candidate = None
                best_mtime = 0
                best_event_count = 0
                best_fr_count = 0
                
                for candidate in cache_files:
                    try:
                        size = os.path.getsize(candidate)
                        if size < 8192:
                            continue
                        mtime = os.path.getmtime(candidate)
                        # 检查是否有数据
                        conn = sqlite3.connect(candidate)
                        event_row = conn.execute("SELECT COUNT(*) FROM behavior_events").fetchone()
                        fr_row = conn.execute("SELECT COUNT(*) FROM analysis_results").fetchone()
                        conn.close()
                        
                        event_count = event_row[0] if event_row else 0
                        fr_count = fr_row[0] if fr_row else 0
                        
                        # 优先选择最近修改的文件，修改时间相同则选事件数多的
                        if mtime > best_mtime or (mtime == best_mtime and event_count > best_event_count):
                            best_mtime = mtime
                            best_event_count = event_count
                            best_fr_count = fr_count
                            best_candidate = candidate
                    except Exception:
                        continue
                
                if best_candidate:
                    db_path = best_candidate
                    logger.info(f"复用已有分析缓存: {db_path}, {best_event_count}个事件, {best_fr_count}条FrameResult, mtime={best_mtime}")
            
            # 如果没有找到合适的已有缓存，创建新的
            if db_path is None:
                db_path = os.path.join(output_dir, f'analysis_results_{int(time.time())}.db')
                logger.info(f"创建新分析缓存: {db_path}")

        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = None
        self._total_records = 0
        self._time_min = None
        self._time_max = None
        self._init_db()
        logger.info(f"AnalysisResultCache 已创建: {db_path}")

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    frame_result TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_analysis_timestamp 
                ON analysis_results(timestamp)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS behavior_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    event_data TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_behavior_time 
                ON behavior_events(start_time, end_time)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        return self._conn

    def _serialize_frame_result(self, frame_result: FrameResult) -> str:
        """将 FrameResult 序列化为 JSON"""
        data = {
            "timestamp": frame_result.timestamp,
            "state": frame_result.state.value if frame_result.state else None,
            "features": asdict(frame_result.features) if frame_result.features else None,
            "event": self._serialize_maneuver_event(frame_result.event) if frame_result.event else None,
            "risk": self._serialize_risk_report(frame_result.risk) if frame_result.risk else None,
            "raw_data": frame_result.raw_data,
            "ax": frame_result.ax,
            "ay": frame_result.ay,
            "az": frame_result.az,
            "gx": frame_result.gx,
            "gy": frame_result.gy,
            "gz": frame_result.gz,
            "speed": frame_result.speed,
            "wheel": frame_result.wheel,
            "loc1": frame_result.loc1,
            "loc2": frame_result.loc2,
            "quality": {k: asdict(v) for k, v in frame_result.quality.items()} if frame_result.quality else {}
        }
        return json.dumps(data, ensure_ascii=False, default=str)
    
    def _serialize_risk_report(self, risk: RiskReport) -> Dict:
        return {
            "level": risk.level.value if risk.level else None,
            "score": risk.score,
            "stability_margin": risk.stability_margin,
            "comfort_index": risk.comfort_index,
            "collision_risk": risk.collision_risk,
            "factors": risk.factors,
        }

    def _serialize_maneuver_event(self, event: ManeuverEvent) -> Dict:
        metadata = dict(event.metadata) if event.metadata else {}
        if 'risk_report' in metadata and hasattr(metadata['risk_report'], 'level'):
            metadata['risk_report'] = self._serialize_risk_report(metadata['risk_report'])
        return {
            "id": event.id,
            "type": event.type,
            "category": event.category.value if event.category else None,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "duration": event.duration,
            "peak_ax": event.peak_ax,
            "peak_ay": event.peak_ay,
            "peak_jerk": event.peak_jerk,
            "speed_range": list(event.speed_range) if event.speed_range else [0.0, 0.0],
            "confidence": event.confidence,
            "detection_method": event.detection_method,
            "risk_level": event.risk_level.value if event.risk_level else None,
            "risk_score": event.risk_score,
            "data_indices": list(event.data_indices) if event.data_indices else [0, 0],
            "metadata": metadata,
        }

    def _deserialize_risk_report(self, data) -> Optional[RiskReport]:
        if data is None:
            return None
        if isinstance(data, RiskReport):
            return data
        if isinstance(data, dict):
            return RiskReport(
                level=RiskLevel(data.get('level', 'SAFE')),
                score=data.get('score', 0.0),
                stability_margin=data.get('stability_margin', 1.0),
                comfort_index=data.get('comfort_index', 0.0),
                collision_risk=data.get('collision_risk', 0.0),
                factors=data.get('factors', {})
            )
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    return self._deserialize_risk_report(parsed)
            except (json.JSONDecodeError, TypeError):
                pass
            import re
            level_match = re.search(r"level=([^,\)]+)", data)
            score_match = re.search(r"score=([\d.]+)", data)
            stability_match = re.search(r"stability_margin=([\d.]+)", data)
            comfort_match = re.search(r"comfort_index=([\d.]+)", data)
            collision_match = re.search(r"collision_risk=([\d.]+)", data)
            level_str = level_match.group(1).strip().strip("'\"") if level_match else 'SAFE'
            try:
                level = RiskLevel(level_str)
            except (ValueError, KeyError):
                level = RiskLevel.SAFE
            return RiskReport(
                level=level,
                score=float(score_match.group(1)) if score_match else 0.0,
                stability_margin=float(stability_match.group(1)) if stability_match else 1.0,
                comfort_index=float(comfort_match.group(1)) if comfort_match else 0.0,
                collision_risk=float(collision_match.group(1)) if collision_match else 0.0,
                factors={}
            )
        return None

    def _deserialize_frame_result(self, data_str: str) -> Optional[FrameResult]:
        """将 JSON 反序列化为 FrameResult"""
        try:
            data = json.loads(data_str)
            
            # 重建 state
            state = DrivingState(data['state']) if data.get('state') else DrivingState.UNKNOWN
            
            # 重建 features
            features = None
            if data.get('features'):
                feat_data = data['features']
                features = FrameFeatures(
                    timestamp=feat_data.get('timestamp', 0.0),
                    temporal=feat_data.get('temporal', {}),
                    spectral=feat_data.get('spectral', {}),
                    kinematic=feat_data.get('kinematic', {}),
                    physics=feat_data.get('physics', {})
                )
            
            # 重建 event
            event = None
            if data.get('event'):
                event_data = data['event']
                category = BehaviorCategory(event_data['category']) if event_data.get('category') else BehaviorCategory.NORMAL
                risk_level = RiskLevel(event_data['risk_level']) if event_data.get('risk_level') else RiskLevel.SAFE
                
                event_metadata = event_data.get('metadata', {})
                if isinstance(event_metadata, dict) and 'risk_report' in event_metadata:
                    event_metadata = dict(event_metadata)
                    event_metadata['risk_report'] = self._deserialize_risk_report(event_metadata['risk_report'])

                event = ManeuverEvent(
                    id=event_data.get('id', ''),
                    type=event_data.get('type', ''),
                    category=category,
                    start_time=event_data.get('start_time', 0.0),
                    end_time=event_data.get('end_time', 0.0),
                    duration=event_data.get('duration', 0.0),
                    peak_ax=event_data.get('peak_ax', 0.0),
                    peak_ay=event_data.get('peak_ay', 0.0),
                    peak_jerk=event_data.get('peak_jerk', 0.0),
                    speed_range=tuple(event_data.get('speed_range', (0.0, 0.0))),
                    confidence=event_data.get('confidence', 0.0),
                    detection_method=event_data.get('detection_method', 'rule_based'),
                    risk_level=risk_level,
                    risk_score=event_data.get('risk_score', 0.0),
                    data_indices=tuple(event_data.get('data_indices', (0, 0))),
                    metadata=event_metadata
                )
            
            # 重建 risk
            risk = None
            if data.get('risk'):
                risk_data = data['risk']
                risk = RiskReport(
                    level=RiskLevel(risk_data.get('level', 'SAFE')),
                    score=risk_data.get('score', 0.0),
                    stability_margin=risk_data.get('stability_margin', 1.0),
                    comfort_index=risk_data.get('comfort_index', 0.0),
                    collision_risk=risk_data.get('collision_risk', 0.0),
                    factors=risk_data.get('factors', {})
                )
            
            # 重建 quality
            quality = {}
            if data.get('quality'):
                for k, v in data['quality'].items():
                    quality[k] = SignalQuality(
                        channel=v.get('channel', k),
                        snr=v.get('snr', 0.0),
                        is_valid=v.get('is_valid', True),
                        outlier_count=v.get('outlier_count', 0),
                        saturation_count=v.get('saturation_count', 0),
                        dropout_count=v.get('dropout_count', 0),
                        flags=v.get('flags', [])
                    )
            
            return FrameResult(
                timestamp=data.get('timestamp', 0.0),
                state=state,
                features=features,
                event=event,
                risk=risk,
                raw_data=data.get('raw_data'),
                ax=data.get('ax', 0.0),
                ay=data.get('ay', 0.0),
                az=data.get('az', 0.0),
                gx=data.get('gx', 0.0),
                gy=data.get('gy', 0.0),
                gz=data.get('gz', 0.0),
                speed=data.get('speed', 0.0),
                wheel=data.get('wheel', 0.0),
                loc1=data.get('loc1', 0.0),
                loc2=data.get('loc2', 0.0),
                quality=quality
            )
        except Exception as e:
            logger.error(f"反序列化 FrameResult 失败: {e}")
            return None

    def write_frame_result(self, frame_result: FrameResult) -> bool:
        """写入单个 FrameResult，同时写入事件（如果有）"""
        try:
            with self._lock:
                conn = self._get_conn()
                frame_result_json = self._serialize_frame_result(frame_result)
                created_at = time.time()
                
                conn.execute(
                    "INSERT INTO analysis_results (timestamp, frame_result, created_at) VALUES (?, ?, ?)",
                    (frame_result.timestamp, frame_result_json, created_at)
                )
                
                if frame_result.event:
                    event_id = getattr(frame_result.event, 'id', '') or getattr(frame_result.event, 'event_id', '')
                    if event_id:
                        existing = conn.execute(
                            "SELECT COUNT(*) FROM behavior_events WHERE json_extract(event_data, '$.id') = ?",
                            (event_id,)
                        ).fetchone()
                        if existing and existing[0] > 0:
                            pass
                        else:
                            event_json = json.dumps(self._serialize_maneuver_event(frame_result.event), ensure_ascii=False, default=str)
                            conn.execute(
                                "INSERT INTO behavior_events (start_time, end_time, event_data, created_at) VALUES (?, ?, ?, ?)",
                                (frame_result.event.start_time, frame_result.event.end_time, event_json, created_at)
                            )
                    else:
                        event_json = json.dumps(self._serialize_maneuver_event(frame_result.event), ensure_ascii=False, default=str)
                        conn.execute(
                            "INSERT INTO behavior_events (start_time, end_time, event_data, created_at) VALUES (?, ?, ?, ?)",
                            (frame_result.event.start_time, frame_result.event.end_time, event_json, created_at)
                        )
                
                conn.commit()
                
                self._total_records += 1
                if self._time_min is None or frame_result.timestamp < self._time_min:
                    self._time_min = frame_result.timestamp
                if self._time_max is None or frame_result.timestamp > self._time_max:
                    self._time_max = frame_result.timestamp
                
                if self._total_records % 1000 == 0:
                    logger.info(f"AnalysisResultCache 已写入 {self._total_records} 条记录")
                
                return True
        except Exception as e:
            logger.error(f"写入 FrameResult 失败: {e}")
            return False

    def write_batch(self, frame_results: List[FrameResult]) -> int:
        """批量写入 FrameResults，同时批量写入事件"""
        if not frame_results:
            return 0
        
        try:
            with self._lock:
                conn = self._get_conn()
                rows = []
                event_rows = []
                seen_event_ids = set()
                created_at = time.time()
                
                existing_ids = set()
                cursor = conn.execute("SELECT json_extract(event_data, '$.id') FROM behavior_events WHERE event_data IS NOT NULL")
                for (eid,) in cursor:
                    if eid:
                        existing_ids.add(eid)
                
                for fr in frame_results:
                    fr_json = self._serialize_frame_result(fr)
                    rows.append((fr.timestamp, fr_json, created_at))
                    
                    if fr.event:
                        event_id = getattr(fr.event, 'id', '') or getattr(fr.event, 'event_id', '')
                        if event_id and (event_id in existing_ids or event_id in seen_event_ids):
                            continue
                        if event_id:
                            seen_event_ids.add(event_id)
                        event_json = json.dumps(self._serialize_maneuver_event(fr.event), ensure_ascii=False, default=str)
                        event_rows.append((fr.event.start_time, fr.event.end_time, event_json, created_at))
                    
                    if self._time_min is None or fr.timestamp < self._time_min:
                        self._time_min = fr.timestamp
                    if self._time_max is None or fr.timestamp > self._time_max:
                        self._time_max = fr.timestamp
                
                conn.executemany(
                    "INSERT INTO analysis_results (timestamp, frame_result, created_at) VALUES (?, ?, ?)",
                    rows
                )
                
                # 批量写入事件
                if event_rows:
                    conn.executemany(
                        "INSERT INTO behavior_events (start_time, end_time, event_data, created_at) VALUES (?, ?, ?, ?)",
                        event_rows
                    )
                
                conn.commit()
                
                count = len(rows)
                self._total_records += count
                
                if self._total_records % 1000 == 0:
                    logger.info(f"AnalysisResultCache 已写入 {self._total_records} 条记录")
                
                return count
        except Exception as e:
            logger.error(f"批量写入 FrameResults 失败: {e}")
            return 0

    def query_time_range(self, start: float, end: float) -> List[FrameResult]:
        """查询指定时间范围内的 FrameResults"""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT frame_result FROM analysis_results WHERE timestamp >= ? AND timestamp <= ? ORDER BY timestamp",
                (start, end)
            )
            results = []
            for (fr_json,) in cursor:
                fr = self._deserialize_frame_result(fr_json)
                if fr:
                    results.append(fr)
            return results

    def get_time_range(self) -> Tuple[float, float]:
        """获取缓存的时间范围"""
        if self._time_min is None or self._time_max is None:
            with self._lock:
                conn = self._get_conn()
                row = conn.execute(
                    "SELECT MIN(timestamp), MAX(timestamp) FROM analysis_results"
                ).fetchone()
                if row[0] is not None:
                    self._time_min = row[0]
                    self._time_max = row[1]
        return (self._time_min or 0.0, self._time_max or 0.0)

    def get_total_records(self) -> int:
        """获取总记录数"""
        if self._total_records == 0:
            with self._lock:
                conn = self._get_conn()
                row = conn.execute(
                    "SELECT COUNT(*) FROM analysis_results"
                ).fetchone()
                self._total_records = row[0]
        return self._total_records

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        t_min, t_max = self.get_time_range()
        return {
            "db_path": self.db_path,
            "total_records": self.get_total_records(),
            "time_range": (t_min, t_max),
            "duration": t_max - t_min if t_min and t_max else 0
        }

    def set_metadata(self, key: str, value: str):
        """设置元数据"""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO cache_metadata (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()

    def get_metadata(self, key: str) -> Optional[str]:
        """获取元数据"""
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT value FROM cache_metadata WHERE key = ?",
                (key,)
            ).fetchone()
            return row[0] if row else None

    def write_maneuver_event(self, event: ManeuverEvent) -> bool:
        """写入单个 ManeuverEvent，带去重检查"""
        try:
            with self._lock:
                conn = self._get_conn()
                event_id = getattr(event, 'id', '')
                
                # 检查事件是否已存在
                if event_id:
                    existing = conn.execute(
                        "SELECT COUNT(*) FROM behavior_events WHERE json_extract(event_data, '$.id') = ?",
                        (event_id,)
                    ).fetchone()
                    if existing and existing[0] > 0:
                        logger.debug(f"事件已存在，跳过写入: {event_id}")
                        return True
                
                event_json = json.dumps(self._serialize_maneuver_event(event), ensure_ascii=False, default=str)
                created_at = time.time()
                
                conn.execute(
                    "INSERT INTO behavior_events (start_time, end_time, event_data, created_at) VALUES (?, ?, ?, ?)",
                    (event.start_time, event.end_time, event_json, created_at)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"写入 ManeuverEvent 失败: {e}")
            return False

    def write_maneuver_events(self, events: List[ManeuverEvent]) -> int:
        """批量写入 ManeuverEvents，带去重检查"""
        if not events:
            return 0
        
        try:
            with self._lock:
                conn = self._get_conn()
                rows = []
                created_at = time.time()
                
                # 先获取数据库中已存在的事件ID
                existing_ids = set()
                cursor = conn.execute("SELECT json_extract(event_data, '$.id') FROM behavior_events WHERE event_data IS NOT NULL")
                for (eid,) in cursor:
                    if eid:
                        existing_ids.add(eid)
                
                count = 0
                for event in events:
                    event_id = getattr(event, 'id', '')
                    
                    # 如果事件ID已存在，则跳过
                    if event_id and event_id in existing_ids:
                        continue
                    
                    # 新增事件ID到已存在集合中，防止本次批量写入内部重复
                    if event_id:
                        existing_ids.add(event_id)
                    
                    event_json = json.dumps(self._serialize_maneuver_event(event), ensure_ascii=False, default=str)
                    rows.append((event.start_time, event.end_time, event_json, created_at))
                    count += 1
                
                if rows:
                    conn.executemany(
                        "INSERT INTO behavior_events (start_time, end_time, event_data, created_at) VALUES (?, ?, ?, ?)",
                        rows
                    )
                    conn.commit()
                    logger.info(f"批量写入 ManeuverEvents: 处理{len(events)}个，写入{count}个，跳过{len(events)-count}个")
                
                return count
        except Exception as e:
            logger.error(f"批量写入 ManeuverEvents 失败: {e}")
            return 0

    def _clear_events(self):
        """清空所有事件（用于重新生成）"""
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM behavior_events")
            conn.commit()
            logger.info("已清空 behavior_events 表")
    
    def clean_duplicate_events(self):
        """清理重复事件，只保留每个事件ID的第一条记录"""
        try:
            with self._lock:
                conn = self._get_conn()
                
                # 查找重复的事件ID
                cursor = conn.execute("""
                    SELECT json_extract(event_data, '$.id') as event_id, COUNT(*) as cnt
                    FROM behavior_events
                    WHERE json_extract(event_data, '$.id') IS NOT NULL
                    GROUP BY event_id
                    HAVING cnt > 1
                """)
                
                duplicates = list(cursor)
                if not duplicates:
                    logger.info("没有发现重复事件")
                    return 0
                
                logger.warning(f"发现 {len(duplicates)} 个重复事件ID，开始清理...")
                total_deleted = 0
                
                for event_id, cnt in duplicates:
                    # 找到每个事件ID的第一条记录
                    first_row = conn.execute("""
                        SELECT rowid FROM behavior_events
                        WHERE json_extract(event_data, '$.id') = ?
                        ORDER BY rowid ASC
                        LIMIT 1
                    """, (event_id,)).fetchone()
                    
                    if first_row:
                        first_rowid = first_row[0]
                        # 删除同一事件ID的其他记录
                        result = conn.execute("""
                            DELETE FROM behavior_events
                            WHERE json_extract(event_data, '$.id') = ?
                            AND rowid != ?
                        """, (event_id, first_rowid))
                        deleted = result.rowcount
                        total_deleted += deleted
                        if deleted > 0:
                            logger.debug(f"清理事件 {event_id}: 删除了 {deleted} 条重复记录")
                
                conn.commit()
                logger.info(f"重复事件清理完成，共删除 {total_deleted} 条记录")
                return total_deleted
        except Exception as e:
            logger.error(f"清理重复事件失败: {e}")
            return 0

    def get_all_maneuver_events(self) -> List[ManeuverEvent]:
        """获取所有 ManeuverEvents"""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT event_data FROM behavior_events ORDER BY start_time"
            )
            events = []
            for (event_json,) in cursor:
                try:
                    event_data = json.loads(event_json)
                    
                    category = BehaviorCategory(event_data['category']) if event_data.get('category') else BehaviorCategory.NORMAL
                    risk_level = RiskLevel(event_data['risk_level']) if event_data.get('risk_level') else RiskLevel.SAFE
                    
                    event_metadata = event_data.get('metadata', {})
                    if isinstance(event_metadata, dict) and 'risk_report' in event_metadata:
                        event_metadata = dict(event_metadata)
                        event_metadata['risk_report'] = self._deserialize_risk_report(event_metadata['risk_report'])

                    event = ManeuverEvent(
                        id=event_data.get('id', ''),
                        type=event_data.get('type', ''),
                        category=category,
                        start_time=event_data.get('start_time', 0.0),
                        end_time=event_data.get('end_time', 0.0),
                        duration=event_data.get('duration', 0.0),
                        peak_ax=event_data.get('peak_ax', 0.0),
                        peak_ay=event_data.get('peak_ay', 0.0),
                        peak_jerk=event_data.get('peak_jerk', 0.0),
                        speed_range=tuple(event_data.get('speed_range', (0.0, 0.0))),
                        confidence=event_data.get('confidence', 0.0),
                        detection_method=event_data.get('detection_method', 'rule_based'),
                        risk_level=risk_level,
                        risk_score=event_data.get('risk_score', 0.0),
                        data_indices=tuple(event_data.get('data_indices', (0, 0))),
                        metadata=event_metadata
                    )
                    events.append(event)
                except Exception as e:
                    logger.warning(f"解析行为事件失败: {e}")
            return events

    def get_events_time_range(self) -> Tuple[float, float]:
        """获取事件的时间范围"""
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT MIN(start_time), MAX(end_time) FROM behavior_events"
            ).fetchone()
            return (row[0] or 0.0, row[1] or 0.0)

    def get_events_count(self) -> int:
        """获取事件总数"""
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT COUNT(*) FROM behavior_events").fetchone()
            return row[0] if row else 0

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info(f"AnalysisResultCache 已关闭: {self.db_path}")

    def __del__(self):
        self.close()

