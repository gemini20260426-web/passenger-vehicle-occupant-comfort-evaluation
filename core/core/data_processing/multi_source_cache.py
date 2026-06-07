#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源数据磁盘缓存 — SQLite + JSON payload
统一存储 CAN/IMU/CNAP 等所有数据源的解析结果

优化特性:
- WAL模式 + NORMAL同步（写入性能优先）
- 批量写入缓冲（减少事务开销）
- 查询结果LRU缓存（减少重复查询）
- 自动清理过期缓存文件
- 最大记录数限制
"""

import json
import sqlite3
import os
import time
import logging
import threading
import glob
from collections import OrderedDict
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_MAX_RECORDS = 15000000
DEFAULT_CACHE_TTL_DAYS = 7
DEFAULT_WRITE_BUFFER_SIZE = 5000
DEFAULT_QUERY_CACHE_SIZE = 32
DEFAULT_WAL_CHECKPOINT_INTERVAL = 50000


class MultiSourceCache:
    """多源数据 SQLite 磁盘缓存"""

    def __init__(self, db_path: str = None, max_records: int = DEFAULT_MAX_RECORDS,
                 cache_ttl_days: int = DEFAULT_CACHE_TTL_DAYS):
        if db_path is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))))),
                'data_output'
            )
            os.makedirs(output_dir, exist_ok=True)
            db_path = os.path.join(output_dir, f'cache_{int(time.time())}.db')

        self.db_path = db_path
        self.max_records = max_records
        self.cache_ttl_days = cache_ttl_days
        self._lock = threading.Lock()
        self._conn = None
        self._total_records = 0
        self._time_min = None
        self._time_max = None
        self._source_types = set()
        self._write_buffer: List[Tuple] = []
        self._write_count_since_checkpoint = 0
        self._query_cache: OrderedDict = OrderedDict()
        self._query_cache_max = DEFAULT_QUERY_CACHE_SIZE
        self._init_db()
        self._cleanup_old_caches()
        logger.info(f"MultiSourceCache 已创建: {db_path} (max_records={max_records}, ttl={cache_ttl_days}d)")

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=OFF")
            conn.execute("PRAGMA cache_size=-128000")
            conn.execute("PRAGMA mmap_size=268435456")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS data_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rel_time REAL NOT NULL,
                    source_type TEXT NOT NULL,
                    channel TEXT,
                    imu_name TEXT,
                    payload TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rel_time
                ON data_records(rel_time)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_source_type
                ON data_records(source_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_channel
                ON data_records(channel)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_source_time
                ON data_records(source_type, rel_time)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    def _cleanup_old_caches(self):
        """清理过期的缓存文件（超过TTL天数的.db文件）"""
        try:
            cache_dir = os.path.dirname(self.db_path)
            if not os.path.isdir(cache_dir):
                return
            now = time.time()
            ttl_seconds = self.cache_ttl_days * 86400
            pattern = os.path.join(cache_dir, 'cache_*.db')
            for fpath in glob.glob(pattern):
                if fpath == self.db_path:
                    continue
                try:
                    mtime = os.path.getmtime(fpath)
                    if now - mtime > ttl_seconds:
                        os.remove(fpath)
                        logger.info(f"已清理过期缓存文件: {os.path.basename(fpath)}")
                except OSError as e:
                    logger.debug(f"清理缓存文件失败: {fpath}, {e}")
        except Exception as e:
            logger.debug(f"清理过期缓存时出错: {e}")

    def _enforce_max_records(self):
        """强制执行最大记录数限制，删除最旧的记录
        注意：调用者（_flush_write_buffer）已持有 self._lock，此处不再加锁避免死锁
        """
        if self.max_records <= 0:
            return
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) FROM data_records").fetchone()
        total = row[0] if row else 0
        if total > self.max_records:
            excess = total - self.max_records
            conn.execute(
                "DELETE FROM data_records WHERE id IN "
                "(SELECT id FROM data_records ORDER BY rel_time ASC LIMIT ?)",
                [excess]
            )
            conn.commit()
            self._total_records = total - excess
            self._invalidate_query_cache()
            logger.info(f"缓存记录数超限，已删除 {excess} 条最旧记录 (当前: {self._total_records})")

    def _invalidate_query_cache(self):
        """使查询缓存失效"""
        self._query_cache.clear()

    def get_cache_size_bytes(self) -> int:
        """获取缓存文件大小（字节）"""
        try:
            return os.path.getsize(self.db_path)
        except OSError:
            return 0

    def get_cache_size_mb(self) -> float:
        """获取缓存文件大小（MB）"""
        return self.get_cache_size_bytes() / (1024 * 1024)

    def clear_expired(self, older_than_seconds: float = None):
        """清除过期数据"""
        if older_than_seconds is None:
            older_than_seconds = self.cache_ttl_days * 86400
        cutoff = time.time() - older_than_seconds
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "DELETE FROM data_records WHERE rel_time < ?", [cutoff]
            )
            deleted = cursor.rowcount
            conn.commit()
            if deleted > 0:
                self._total_records = max(0, self._total_records - deleted)
                self._invalidate_query_cache()
                logger.info(f"已清除 {deleted} 条过期数据")
            return deleted

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        return self._conn

    def _detect_source_type(self, record: Dict[str, Any]) -> str:
        if '_source_type' in record and record['_source_type'] not in ('', 'unknown'):
            return record['_source_type']
        if 'cnap_type' in record:
            return 'cnap_' + record['cnap_type'].lower()
        if 'pressure' in record and 'cnap_type' not in record:
            return 'cnap_wave'
        if '_imu_name' in record and 'Ax_m_s2' in record:
            return 'can_long'
        if 'imu_name' in record and 'Ax_m_s2' in record:
            return 'can_long'
        if any(k.startswith('ch') and '_ax' in k for k in record):
            return 'can_wide'
        if any(k in record for k in ('ax', 'ay', 'az', 'gx', 'gy', 'gz')):
            return 'pipeline'
        return 'unknown'

    def _extract_rel_time(self, record: Dict[str, Any]) -> float:
        return record.get('rel_time', record.get('timestamp',
            record.get('wave_t', record.get('beat_t', 0.0))))

    def _extract_channel(self, record: Dict[str, Any]) -> Optional[str]:
        return record.get('channel', record.get('ch', None))

    def _extract_imu_name(self, record: Dict[str, Any]) -> Optional[str]:
        return record.get('imu_name', None)

    @staticmethod
    def _sanitize_for_json(obj: Any) -> Any:
        """递归预处理数据，将 bytes 转为 hex 字符串，避免 json.dumps 序列化异常"""
        if isinstance(obj, bytes):
            return obj.hex()
        if isinstance(obj, dict):
            return {k: MultiSourceCache._sanitize_for_json(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [MultiSourceCache._sanitize_for_json(v) for v in obj]
        return obj

    def write_batch(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0

        with self._lock:
            rows = []
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                source_type = self._detect_source_type(rec)
                rel_time = self._extract_rel_time(rec)
                channel = self._extract_channel(rec)
                imu_name = self._extract_imu_name(rec)
                sanitized = self._sanitize_for_json(rec)
                payload = json.dumps(sanitized, ensure_ascii=False, default=str)

                rows.append((rel_time, source_type, channel, imu_name, payload))

                if self._time_min is None or rel_time < self._time_min:
                    self._time_min = rel_time
                if self._time_max is None or rel_time > self._time_max:
                    self._time_max = rel_time
                self._source_types.add(source_type)

            self._write_buffer.extend(rows)

            if len(self._write_buffer) >= DEFAULT_WRITE_BUFFER_SIZE:
                self._flush_write_buffer()

            return len(rows)

    def _flush_write_buffer(self):
        """将写缓冲区的数据批量提交到SQLite"""
        if not self._write_buffer:
            return
        conn = self._get_conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.executemany(
                "INSERT INTO data_records (rel_time, source_type, channel, imu_name, payload) "
                "VALUES (?, ?, ?, ?, ?)",
                self._write_buffer
            )
            conn.commit()
            flushed = len(self._write_buffer)
            self._total_records += flushed
            self._write_count_since_checkpoint += flushed
            self._write_buffer.clear()
            self._invalidate_query_cache()

            if self._total_records % 5000 == 0:
                logger.info(f"缓存已写入 {self._total_records} 条记录")

            if self._write_count_since_checkpoint >= DEFAULT_WAL_CHECKPOINT_INTERVAL:
                self._wal_checkpoint()
                self._write_count_since_checkpoint = 0

            self._enforce_max_records()
        except Exception:
            conn.rollback()
            raise

    def _wal_checkpoint(self):
        """执行WAL检查点，将WAL数据合并回主数据库"""
        try:
            conn = self._get_conn()
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception as e:
            logger.debug(f"WAL checkpoint 失败: {e}")

    def flush(self):
        """强制刷新写缓冲区（在关闭缓存前调用）"""
        with self._lock:
            self._flush_write_buffer()

    def query_time_range(self, start: float, end: float,
                         source_types: List[str] = None) -> List[Dict[str, Any]]:
        cache_key = self._make_query_cache_key(start, end, source_types)
        if cache_key in self._query_cache:
            self._query_cache.move_to_end(cache_key)
            return self._query_cache[cache_key]

        with self._lock:
            conn = self._get_conn()
            if source_types:
                placeholders = ','.join('?' * len(source_types))
                sql = (f"SELECT source_type, rel_time, payload FROM data_records "
                       f"WHERE rel_time >= ? AND rel_time <= ? "
                       f"AND source_type IN ({placeholders}) "
                       f"ORDER BY rel_time")
                params = [start, end] + source_types
            else:
                sql = ("SELECT source_type, rel_time, payload FROM data_records "
                       "WHERE rel_time >= ? AND rel_time <= ? "
                       "ORDER BY rel_time")
                params = [start, end]

            cursor = conn.execute(sql, params)
            results = []
            for (source_type, rel_time, payload) in cursor:
                try:
                    record = json.loads(payload)
                    record['_source_type'] = source_type
                    record['_rel_time'] = rel_time
                    results.append(record)
                except json.JSONDecodeError:
                    continue

            self._add_to_query_cache(cache_key, results)
            return results

    # ─────────── SQLite 直读 API（绕过 JSON 逐条解析，大幅提升性能）───────────

    # can_wide 格式 gyro 单位转换常量: deg/s → rad/s
    _DEG_TO_RAD = 3.141592653589793 / 180.0
    # 速度单位转换: km/h → m/s
    _KMH_TO_MS = 1000.0 / 3600.0

    @staticmethod
    def _extract_can_wide_value(d: Dict[str, Any], ch: str, field_patterns: List[str]) -> float:
        """从 can_wide 格式字典中提取指定通道的字段值"""
        for pat in field_patterns:
            key = f'{ch}_{pat}'
            if key in d:
                return float(d.get(key, 0) or 0)
        return 0.0

    @staticmethod
    def _parse_raw_csv_timestamp(ts_str: str) -> float:
        """将原始 CSV 时间戳 (HH:MM:SS.ffffff) 转为绝对秒数"""
        try:
            parts = ts_str.strip().split(':')
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        except (ValueError, AttributeError):
            pass
        return 0.0

    def query_imu_numpy(self, start: float = None, end: float = None,
                        source_types: List[str] = None):
        """直接查询 SQLite 并返回 numpy 数组。
        返回 (t, ax, ay, az, gx, gy, gz, speed, wheel) 各为 1D array。
        用于 IMU 可视化一键加载，避免 json.loads × 10 万次。
        支持 raw CSV / can_wide / can_long / pipeline 四种数据格式。
        """
        import numpy as np

        t_list, ax_list, ay_list, az_list = [], [], [], []
        gx_list, gy_list, gz_list = [], [], []
        speed_list, wheel_list = [], []

        # 格式检测缓存：只检测前若干条记录，后续复用
        _format_detected = None  # 'raw_csv' | 'can_wide' | 'standard'
        _can_wide_ch = None
        _format_check_count = 0
        _FORMAT_CHECK_MAX = 50
        _t0 = None  # 首条记录绝对时间，用于计算相对时间
        _speed_kmh = None  # 速度单位检测

        with self._lock:
            conn = self._get_conn()
            if start is not None or end is not None:
                conditions = []
                params = []
                if start is not None:
                    conditions.append("rel_time >= ?")
                    params.append(start)
                if end is not None:
                    conditions.append("rel_time <= ?")
                    params.append(end)
                if source_types:
                    placeholders = ','.join('?' * len(source_types))
                    conditions.append(f"source_type IN ({placeholders})")
                    params.extend(source_types)
                where_clause = " AND ".join(conditions)
                sql = (f"SELECT rel_time, payload FROM data_records "
                       f"WHERE {where_clause} ORDER BY rel_time")
                cursor = conn.execute(sql, params)
            elif source_types:
                placeholders = ','.join('?' * len(source_types))
                sql = (f"SELECT rel_time, payload FROM data_records "
                       f"WHERE source_type IN ({placeholders}) ORDER BY rel_time")
                cursor = conn.execute(sql, source_types)
            else:
                sql = "SELECT rel_time, payload FROM data_records ORDER BY rel_time"
                cursor = conn.execute(sql)

            for rel_time, payload in cursor:
                try:
                    d = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                # ── 格式检测：前 N 条记录判断数据格式 ──
                if _format_detected is None and _format_check_count < _FORMAT_CHECK_MAX:
                    _format_check_count += 1
                    # 1) raw CSV 格式（CANFullParser 失败回退产物）
                    if 'raw' in d:
                        _format_detected = 'raw_csv'
                        logging.getLogger(__name__).info(
                            "query_imu_numpy: 检测到 raw CSV 格式")
                    # 2) can_wide 格式（ch*_ax 等字段）
                    elif any(k.startswith('ch') and ('_ax' in k or '_f0_Accel' in k) for k in d):
                        _format_detected = 'can_wide'
                        for ch in ('ch1', 'ch3', 'ch4', 'ch5', 'ch2', 'ch6', 'ch7', 'ch8', 'ch9', 'ch10'):
                            if f'{ch}_ax' in d or f'{ch}_f0_Accel_m/s2' in d:
                                _can_wide_ch = ch
                                logging.getLogger(__name__).info(
                                    f"query_imu_numpy: 检测到 can_wide 格式，使用通道 {_can_wide_ch}")
                                break
                        if not _can_wide_ch:
                            _can_wide_ch = 'ch1'
                    # 3) 标准格式（can_long / pipeline / IMU standalone）
                    else:
                        _format_detected = 'standard'

                # ── 提取数据 ──
                if _format_detected == 'raw_csv':
                    # raw CSV 格式: "HH:MM:SS.ffffff,speed_kmh,wheel_angle,,,,,..."
                    # CAN 总线原始数据，速度单位为 km/h，需转换为 m/s
                    parts = d['raw'].split(',')
                    ts_abs = self._parse_raw_csv_timestamp(parts[0]) if parts else 0.0
                    if _t0 is None:
                        _t0 = ts_abs
                    t_list.append(ts_abs - _t0)

                    raw_speed_kmh = float(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else 0.0
                    raw_wheel = float(parts[2].strip()) if len(parts) > 2 and parts[2].strip() else 0.0

                    # raw CSV 格式速度始终为 km/h，直接转换为 m/s
                    speed_list.append(raw_speed_kmh * self._KMH_TO_MS)
                    wheel_list.append(raw_wheel)
                    ax_list.append(0.0)
                    ay_list.append(0.0)
                    az_list.append(0.0)
                    gx_list.append(0.0)
                    gy_list.append(0.0)
                    gz_list.append(0.0)

                elif _format_detected == 'can_wide' and _can_wide_ch:
                    # ── can_wide 格式：从指定通道提取 ──
                    t_list.append(rel_time)
                    ch = _can_wide_ch
                    ax_list.append(self._extract_can_wide_value(
                        d, ch, ['f0_Accel_m/s2', 'ax', 'Ax_m_s2']))
                    ay_list.append(self._extract_can_wide_value(
                        d, ch, ['f1_Accel_m/s2', 'ay', 'Ay_m_s2']))
                    az_list.append(self._extract_can_wide_value(
                        d, ch, ['f2_Accel_m/s2', 'az', 'Az_m_s2', 'f11_AccelZ_m/s2']))
                    gx_dps = self._extract_can_wide_value(
                        d, ch, ['f3_Gyro_dps', 'gx', 'Gx_dps'])
                    gy_dps = self._extract_can_wide_value(
                        d, ch, ['f4_Gyro_dps', 'gy', 'Gy_dps'])
                    gz_dps = self._extract_can_wide_value(
                        d, ch, ['f5_Gyro_dps', 'gz', 'Gz_dps'])
                    gx_list.append(gx_dps * self._DEG_TO_RAD)
                    gy_list.append(gy_dps * self._DEG_TO_RAD)
                    gz_list.append(gz_dps * self._DEG_TO_RAD)
                    raw_speed = float(d.get('speed', d.get('车速_kmh', 0)) or 0)
                    speed_list.append(raw_speed)
                    wheel_list.append(float(d.get('steering', d.get('方向盘转角_deg', 0)) or 0))

                else:
                    # ── 标准格式：can_long / pipeline / IMU standalone ──
                    t_list.append(rel_time)
                    ax_list.append(float(d.get('ax', d.get('Ax_m_s2', 0)) or 0))
                    ay_list.append(float(d.get('ay', d.get('Ay_m_s2', 0)) or 0))
                    az_list.append(float(d.get('az', d.get('Az_m_s2', 0)) or 0))
                    gx_list.append(float(d.get('gx', d.get('Gx_rad_s', 0)) or 0))
                    gy_list.append(float(d.get('gy', d.get('Gy_rad_s', 0)) or 0))
                    gz_list.append(float(d.get('gz', d.get('Gz_rad_s', 0)) or 0))
                    speed_list.append(float(d.get('speed', d.get('车速_kmh', 0)) or 0))
                    wheel_list.append(float(d.get('wheel', d.get('方向盘转角_deg', 0)) or 0))

            # ── 若速度单位未确定，对全量数据做一次检测并统一转换 ──
            if _speed_kmh is None and speed_list and _format_detected != 'raw_csv':
                high_count = sum(1 for v in speed_list if v > 50)
                _speed_kmh = high_count > len(speed_list) * 0.1
                if _speed_kmh:
                    speed_list = [v * self._KMH_TO_MS for v in speed_list]

        if not t_list:
            return (np.array([]), np.array([]), np.array([]), np.array([]),
                    np.array([]), np.array([]), np.array([]),
                    np.array([]), np.array([]))

        return (np.array(t_list, dtype=np.float64),
                np.array(ax_list, dtype=np.float64),
                np.array(ay_list, dtype=np.float64),
                np.array(az_list, dtype=np.float64),
                np.array(gx_list, dtype=np.float64),
                np.array(gy_list, dtype=np.float64),
                np.array(gz_list, dtype=np.float64),
                np.array(speed_list, dtype=np.float64),
                np.array(wheel_list, dtype=np.float64))

    def query_records_raw(self, start: float = None, end: float = None,
                          source_types: List[str] = None) -> List[Dict[str, Any]]:
        """类似 query_time_range 但只返回完整记录，用于批量喂入 pipeline。
        返回的记录已展开 payload 字段到顶层（rel_time, speed, wheel, ax/ay/az/gx/gy/gz 等）。
        """
        _t0 = None
        with self._lock:
            conn = self._get_conn()
            conditions = []
            params = []
            if start is not None:
                conditions.append("rel_time >= ?")
                params.append(start)
            if end is not None:
                conditions.append("rel_time <= ?")
                params.append(end)
            if source_types:
                placeholders = ','.join('?' * len(source_types))
                conditions.append(f"source_type IN ({placeholders})")
                params.extend(source_types)

            if conditions:
                where_clause = " AND ".join(conditions)
                sql = (f"SELECT source_type, rel_time, channel, imu_name, payload FROM data_records "
                       f"WHERE {where_clause} ORDER BY rel_time")
            else:
                sql = "SELECT source_type, rel_time, channel, imu_name, payload FROM data_records ORDER BY rel_time"

            cursor = conn.execute(sql, params)
            results = []
            for (source_type, rel_time, channel, imu_name, payload) in cursor:
                try:
                    d = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                # ── raw CSV 格式回退 ──
                if 'raw' in d:
                    parts = d['raw'].split(',')
                    ts_abs = self._parse_raw_csv_timestamp(parts[0]) if parts else 0.0
                    if _t0 is None:
                        _t0 = ts_abs
                    t = ts_abs - _t0

                    raw_speed = float(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else 0.0
                    raw_wheel = float(parts[2].strip()) if len(parts) > 2 and parts[2].strip() else 0.0

                    record = {
                        '_source_type': source_type,
                        'channel': channel or '',
                        'imu_name': imu_name or '',
                        'rel_time': t,
                        'timestamp': t,
                        't': t,
                        'ax': 0.0, 'ay': 0.0, 'az': 0.0,
                        'gx': 0.0, 'gy': 0.0, 'gz': 0.0,
                        'speed': raw_speed * self._KMH_TO_MS,
                        'wheel': raw_wheel,
                        '_source_name': '',
                    }
                    results.append(record)
                    continue

                # 展开到顶层，保持与 _normalize_can_record 输出一致的字段名
                record = {
                    '_source_type': source_type,
                    'channel': channel or d.get('channel', d.get('ch', '')),
                    'imu_name': imu_name or d.get('imu_name', d.get('imu', '')),
                    'rel_time': rel_time,
                    'timestamp': rel_time,
                    't': rel_time,
                    'ax': float(d.get('ax', d.get('Ax_m_s2', 0)) or 0),
                    'ay': float(d.get('ay', d.get('Ay_m_s2', 0)) or 0),
                    'az': float(d.get('az', d.get('Az_m_s2', 0)) or 0),
                    'gx': float(d.get('gx', d.get('Gx_rad_s', 0)) or 0),
                    'gy': float(d.get('gy', d.get('Gy_rad_s', 0)) or 0),
                    'gz': float(d.get('gz', d.get('Gz_rad_s', 0)) or 0),
                    'speed': float(d.get('speed', d.get('车速_kmh', 0)) or 0),
                    'wheel': float(d.get('wheel', d.get('方向盘转角_deg', 0)) or 0),
                    '_source_name': d.get('imu_name', d.get('_source_name', '')),
                }
                results.append(record)
            return results

    def get_data_stats(self) -> Dict[str, Any]:
        """快速获取数据摘要（count, time_range, source_types）"""
        t_min, t_max = self.get_time_range()
        return {
            'total_records': self.get_total_records(),
            'time_min': t_min or 0.0,
            'time_max': t_max or 0.0,
            'duration': (t_max - t_min) if (t_min is not None and t_max is not None) else 0,
            'source_types': self.get_source_types(),
        }

    def _make_query_cache_key(self, start: float, end: float,
                               source_types: List[str] = None) -> str:
        st_key = ','.join(sorted(source_types)) if source_types else '*'
        return f"{start:.6f}_{end:.6f}_{st_key}"

    def _add_to_query_cache(self, key: str, results: List[Dict[str, Any]]):
        if len(self._query_cache) >= self._query_cache_max:
            self._query_cache.popitem(last=False)
        self._query_cache[key] = results

    def get_time_range(self) -> Tuple[float, float]:
        if self._time_min is None or self._time_max is None:
            with self._lock:
                conn = self._get_conn()
                row = conn.execute(
                    "SELECT MIN(rel_time), MAX(rel_time) FROM data_records"
                ).fetchone()
                if row[0] is not None:
                    self._time_min = row[0]
                    self._time_max = row[1]
        return (self._time_min or 0.0, self._time_max or 0.0)

    def get_time_range_for_sources(self, source_types: List[str]) -> Tuple[Optional[float], Optional[float]]:
        if not source_types:
            return self.get_time_range()
        with self._lock:
            conn = self._get_conn()
            placeholders = ','.join('?' * len(source_types))
            row = conn.execute(
                f"SELECT MIN(rel_time), MAX(rel_time) FROM data_records WHERE source_type IN ({placeholders})",
                source_types
            ).fetchone()
            if row[0] is not None:
                return (row[0], row[1])
        return (None, None)

    def query_by_source_type(self, source_type: str, limit: int = None,
                             offset: int = 0) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            if limit is not None:
                sql = ("SELECT source_type, rel_time, payload FROM data_records "
                       "WHERE source_type = ? "
                       "ORDER BY rel_time LIMIT ? OFFSET ?")
                params = [source_type, limit, offset]
            else:
                sql = ("SELECT source_type, rel_time, payload FROM data_records "
                       "WHERE source_type = ? "
                       "ORDER BY rel_time")
                params = [source_type]

            cursor = conn.execute(sql, params)
            results = []
            for (st, rel_time, payload) in cursor:
                try:
                    record = json.loads(payload)
                    record['_source_type'] = st
                    record['_rel_time'] = rel_time
                    results.append(record)
                except json.JSONDecodeError:
                    continue
            return results

    def count_by_source_type(self, source_type: str) -> int:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT COUNT(*) FROM data_records WHERE source_type = ?",
                [source_type]
            ).fetchone()
            return row[0] if row else 0

    def get_source_types(self) -> List[str]:
        if not self._source_types:
            with self._lock:
                conn = self._get_conn()
                rows = conn.execute(
                    "SELECT DISTINCT source_type FROM data_records"
                ).fetchall()
                self._source_types = set(r[0] for r in rows)
        return sorted(self._source_types)

    def get_total_records(self) -> int:
        if self._total_records == 0:
            with self._lock:
                conn = self._get_conn()
                row = conn.execute(
                    "SELECT COUNT(*) FROM data_records"
                ).fetchone()
                self._total_records = row[0]
        return self._total_records

    def get_stats(self) -> Dict[str, Any]:
        t_min, t_max = self.get_time_range()
        return {
            'db_path': self.db_path,
            'total_records': self.get_total_records(),
            'time_range': (t_min, t_max),
            'duration': t_max - t_min if t_min and t_max else 0,
            'source_types': self.get_source_types(),
            'cache_size_mb': round(self.get_cache_size_mb(), 2),
            'max_records': self.max_records,
            'cache_ttl_days': self.cache_ttl_days,
            'write_buffer_pending': len(self._write_buffer),
            'query_cache_entries': len(self._query_cache),
        }

    def close(self):
        if self._conn:
            self.flush()
            self._wal_checkpoint()
            self._conn.close()
            self._conn = None
            logger.info(f"MultiSourceCache 已关闭: {self.db_path}")

    def _clear_db(self):
        if not self._conn:
            try:
                self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            except Exception:
                return
        try:
            for table in ['cache_data', 'event_cache', 'cache_metadata']:
                self._conn.execute(f"DELETE FROM {table}")
            self._conn.commit()
            self._wal_checkpoint()
            self._insertion_count = 0
            self._query_cache.clear()
            logger.info(f"MultiSourceCache 数据库表已清空: {self.db_path}")
        except Exception:
            pass

    def __del__(self):
        self.close()