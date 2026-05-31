#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存注册表 (CacheRegistry)
管理所有历史缓存数据集的索引，支持缓存选择、注册、删除。
"""

import os
import glob
import sqlite3
import uuid
import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存数据集条目"""
    id: str                            # UUID
    cache_db_path: str                 # cache_xxx.db 路径
    analysis_db_path: str = ''         # analysis_results_xxx.db 路径（可选）
    source_files: List[str] = field(default_factory=list)   # 原始数据源文件名
    source_types: List[str] = field(default_factory=list)   # 数据类型
    imu_channels: List[str] = field(default_factory=list)   # IMU 通道列表
    time_range: Tuple[float, float] = (0.0, 0.0)            # (min_ts, max_ts)
    record_count: int = 0              # 总记录数
    event_count: int = 0               # 事件数
    creation_time: float = 0.0         # 创建时间戳
    data_format: str = '1.0'           # 数据格式版本

    @property
    def duration(self) -> float:
        """数据时长（秒）"""
        return max(0.0, self.time_range[1] - self.time_range[0])

    @property
    def display_label(self) -> str:
        """生成用于 UI 下拉框的显示标签"""
        import datetime
        ts_str = datetime.datetime.fromtimestamp(self.creation_time).strftime('%Y-%m-%d %H:%M')
        types_str = ' + '.join(self.source_types[:3]) if self.source_types else '未知'
        if len(self.source_types) > 3:
            types_str += f' +{len(self.source_types) - 3}'
        evt_str = f'{self.event_count}事件' if self.event_count > 0 else '无事件'
        return f'[{ts_str}] {types_str} | {self.record_count}条 | {evt_str}'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'cache_db_path': self.cache_db_path,
            'analysis_db_path': self.analysis_db_path,
            'source_files': self.source_files,
            'source_types': self.source_types,
            'imu_channels': self.imu_channels,
            'time_min': self.time_range[0],
            'time_max': self.time_range[1],
            'record_count': self.record_count,
            'event_count': self.event_count,
            'creation_time': self.creation_time,
            'data_format': self.data_format,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'CacheEntry':
        return cls(
            id=d.get('id', ''),
            cache_db_path=d.get('cache_db_path', ''),
            analysis_db_path=d.get('analysis_db_path', ''),
            source_files=d.get('source_files', []),
            source_types=d.get('source_types', []),
            imu_channels=d.get('imu_channels', []),
            time_range=(d.get('time_min', 0.0), d.get('time_max', 0.0)),
            record_count=d.get('record_count', 0),
            event_count=d.get('event_count', 0),
            creation_time=d.get('creation_time', 0.0),
            data_format=d.get('data_format', '1.0'),
        )


class CacheRegistry:
    """缓存注册表 — 管理所有历史缓存数据集索引"""

    def __init__(self, data_dir: str):
        self._data_dir = data_dir
        self._index_db = os.path.join(data_dir, 'cache_registry.db')
        self._entries: Dict[str, CacheEntry] = {}
        self._default_id: Optional[str] = None
        self._ensure_tables()
        self._load_all()
        self._scan_and_register()
        logger.info(f"CacheRegistry 已初始化: {data_dir}, {len(self._entries)} 个已注册缓存")

    # ── SQLite 表结构 ──────────────────────────────────────────

    def _ensure_tables(self):
        """确保索引表存在"""
        with sqlite3.connect(self._index_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_index (
                    id TEXT PRIMARY KEY,
                    cache_db_path TEXT NOT NULL,
                    analysis_db_path TEXT DEFAULT '',
                    source_files TEXT DEFAULT '[]',
                    source_types TEXT DEFAULT '[]',
                    imu_channels TEXT DEFAULT '[]',
                    time_min REAL DEFAULT 0.0,
                    time_max REAL DEFAULT 0.0,
                    record_count INTEGER DEFAULT 0,
                    event_count INTEGER DEFAULT 0,
                    creation_time REAL DEFAULT 0.0,
                    data_format TEXT DEFAULT '1.0',
                    is_default INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def _load_all(self):
        """从 SQLite 加载所有缓存条目"""
        self._entries.clear()
        try:
            with sqlite3.connect(self._index_db) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM cache_index ORDER BY creation_time DESC"
                ).fetchall()
            for row in rows:
                entry = CacheEntry(
                    id=row['id'],
                    cache_db_path=row['cache_db_path'],
                    analysis_db_path=row['analysis_db_path'],
                    source_files=self._json_decode(row['source_files']),
                    source_types=self._json_decode(row['source_types']),
                    imu_channels=self._json_decode(row['imu_channels']),
                    time_range=(row['time_min'], row['time_max']),
                    record_count=row['record_count'],
                    event_count=row['event_count'],
                    creation_time=row['creation_time'],
                    data_format=row['data_format'],
                )
                self._entries[entry.id] = entry
                if row['is_default']:
                    self._default_id = entry.id
        except Exception as e:
            logger.warning(f"加载缓存索引失败: {e}")

    # ── 扫描与注册 ─────────────────────────────────────────────

    def _scan_and_register(self):
        """扫描 data_output 目录，注册未记录的缓存文件"""
        cache_files = glob.glob(os.path.join(self._data_dir, 'cache_*.db'))
        new_count = 0
        for cache_path in cache_files:
            cache_name = os.path.basename(cache_path)
            ts_str = cache_name.replace('cache_', '').replace('.db', '')
            # 检查是否已注册
            if cache_path in {e.cache_db_path for e in self._entries.values()}:
                continue
            # 提取元数据
            metadata = self._extract_cache_metadata(cache_path)
            if metadata['record_count'] == 0:
                continue
            # 查找对应的分析缓存
            analysis_path = os.path.join(self._data_dir, f'analysis_results_{ts_str}.db')
            if not os.path.exists(analysis_path):
                analysis_path = ''
            # 提取分析缓存事件数
            event_count = 0
            if analysis_path:
                event_count = self._count_events_in_analysis_cache(analysis_path)
            entry = CacheEntry(
                id=str(uuid.uuid4()),
                cache_db_path=cache_path,
                analysis_db_path=analysis_path,
                source_files=metadata.get('source_files', []),
                source_types=metadata.get('source_types', []),
                imu_channels=metadata.get('imu_channels', []),
                time_range=metadata.get('time_range', (0.0, 0.0)),
                record_count=metadata.get('record_count', 0),
                event_count=event_count,
                creation_time=os.path.getmtime(cache_path),
            )
            self._save_entry(entry)
            self._entries[entry.id] = entry
            new_count += 1
        if new_count > 0:
            logger.info(f"扫描发现 {new_count} 个新缓存文件，已自动注册")
        # 设置默认缓存（最新）
        if self._entries and self._default_id is None:
            latest = max(self._entries.values(), key=lambda e: e.creation_time)
            self._set_default(latest.id)

    def _extract_cache_metadata(self, cache_path: str) -> Dict[str, Any]:
        """从 cache_xxx.db 提取元数据"""
        metadata = {
            'source_files': [], 'source_types': [],
            'imu_channels': [], 'time_range': (0.0, 0.0),
            'record_count': 0,
        }
        try:
            conn = sqlite3.connect(cache_path)
            # 记录总数
            row = conn.execute("SELECT COUNT(*) FROM data_records").fetchone()
            metadata['record_count'] = row[0] if row else 0
            if metadata['record_count'] == 0:
                conn.close()
                return metadata
            # 数据源类型
            rows = conn.execute(
                "SELECT DISTINCT source_type FROM data_records"
            ).fetchall()
            metadata['source_types'] = [r[0] for r in rows if r[0]]
            # 时间范围
            rng = conn.execute(
                "SELECT MIN(rel_time), MAX(rel_time) FROM data_records"
            ).fetchone()
            if rng and rng[0] is not None:
                metadata['time_range'] = (rng[0], rng[1])
            # IMU 通道
            if 'can_wide' in metadata['source_types'] or 'can_long' in metadata['source_types']:
                imu_rows = conn.execute(
                    "SELECT DISTINCT imu_name FROM data_records WHERE imu_name IS NOT NULL AND imu_name != ''"
                ).fetchall()
                metadata['imu_channels'] = [r[0] for r in imu_rows if r[0]]
            conn.close()
        except Exception as e:
            logger.warning(f"提取缓存元数据失败 ({cache_path}): {e}")
        return metadata

    def _count_events_in_analysis_cache(self, analysis_path: str) -> int:
        """统计分析缓存中的事件数"""
        try:
            conn = sqlite3.connect(analysis_path)
            row = conn.execute("SELECT COUNT(*) FROM behavior_events").fetchone()
            conn.close()
            return row[0] if row else 0
        except Exception:
            return 0

    # ── CRUD 操作 ──────────────────────────────────────────────

    def _save_entry(self, entry: CacheEntry):
        """将条目写入 SQLite"""
        try:
            with sqlite3.connect(self._index_db) as conn:
                is_default = 1 if entry.id == self._default_id else 0
                conn.execute("""
                    INSERT OR REPLACE INTO cache_index
                    (id, cache_db_path, analysis_db_path, source_files, source_types,
                     imu_channels, time_min, time_max, record_count, event_count,
                     creation_time, data_format, is_default)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.id,
                    entry.cache_db_path,
                    entry.analysis_db_path,
                    self._json_encode(entry.source_files),
                    self._json_encode(entry.source_types),
                    self._json_encode(entry.imu_channels),
                    entry.time_range[0],
                    entry.time_range[1],
                    entry.record_count,
                    entry.event_count,
                    entry.creation_time,
                    entry.data_format,
                    is_default,
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"保存缓存条目失败: {e}")

    def register(self, cache_path: str, analysis_path: str = '',
                 metadata: Optional[Dict[str, Any]] = None,
                 force: bool = False) -> Optional[str]:
        """注册新缓存，返回 cache_id。
        
        Args:
            force: 若为 True，即使 record_count==0 也注册（用于预注册空缓存）
        """
        if metadata is None:
            metadata = self._extract_cache_metadata(cache_path)
        if metadata['record_count'] == 0 and not force:
            return None
        event_count = 0
        if analysis_path:
            event_count = self._count_events_in_analysis_cache(analysis_path)
        entry = CacheEntry(
            id=str(uuid.uuid4()),
            cache_db_path=cache_path,
            analysis_db_path=analysis_path,
            source_files=metadata.get('source_files', []),
            source_types=metadata.get('source_types', []),
            imu_channels=metadata.get('imu_channels', []),
            time_range=metadata.get('time_range', (0.0, 0.0)),
            record_count=metadata['record_count'],
            event_count=event_count,
            creation_time=time.time(),
        )
        self._save_entry(entry)
        self._entries[entry.id] = entry
        if self._default_id is None:
            self._set_default(entry.id)
        logger.info(f"已注册新缓存: {entry.id[:8]}... → {os.path.basename(cache_path)}")
        return entry.id

    def list_caches(self) -> List[CacheEntry]:
        """返回所有缓存条目（按创建时间降序）"""
        return sorted(self._entries.values(),
                      key=lambda e: e.creation_time, reverse=True)

    def get_entry(self, cache_id: str) -> Optional[CacheEntry]:
        """根据 id 获取缓存条目"""
        return self._entries.get(cache_id)

    def get_cache(self, cache_id: str) -> Tuple[Any, Any]:
        """
        加载指定缓存的数据对象。
        返回 (MultiSourceCache, AnalysisResultCache)
        """
        entry = self._entries.get(cache_id)
        if not entry:
            raise ValueError(f"缓存条目不存在: {cache_id}")
        from core.core.data_processing.multi_source_cache import MultiSourceCache
        cache = MultiSourceCache(db_path=entry.cache_db_path)
        analysis_cache = None
        if entry.analysis_db_path and os.path.exists(entry.analysis_db_path):
            from core.core.analysis.analysis_result_cache import AnalysisResultCache
            analysis_cache = AnalysisResultCache(
                output_dir=self._data_dir,
                cache=cache
            )
            # 尝试复用已有 db_path
            if hasattr(analysis_cache, 'db_path'):
                try:
                    analysis_cache.db_path = entry.analysis_db_path
                except Exception:
                    pass
        return cache, analysis_cache

    def delete(self, cache_id: str) -> bool:
        """删除缓存记录及对应 .db 文件"""
        entry = self._entries.pop(cache_id, None)
        if not entry:
            return False
        try:
            with sqlite3.connect(self._index_db) as conn:
                conn.execute("DELETE FROM cache_index WHERE id = ?", (cache_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"从索引删除缓存失败: {e}")
        # 删除实际文件
        for path in [entry.cache_db_path, entry.analysis_db_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info(f"已删除缓存文件: {os.path.basename(path)}")
                except Exception as e:
                    logger.warning(f"删除缓存文件失败 ({path}): {e}")
        if cache_id == self._default_id:
            self._default_id = None
            if self._entries:
                latest = max(self._entries.values(), key=lambda e: e.creation_time)
                self._set_default(latest.id)
        return True

    def refresh_entry(self, cache_db_path: str) -> bool:
        """刷新已注册缓存条目的元数据（用于缓存内容变更后更新）"""
        abs_path = os.path.abspath(cache_db_path)
        # 查找匹配的条目
        target_id = None
        for eid, entry in self._entries.items():
            if os.path.abspath(entry.cache_db_path) == abs_path:
                target_id = eid
                break
        if not target_id:
            logger.warning(f"refresh_entry: 未找到已注册缓存 {abs_path}")
            return False
        entry = self._entries[target_id]
        # 重新提取元数据
        metadata = self._extract_cache_metadata(abs_path)
        if metadata['record_count'] == 0:
            return False
        entry.record_count = metadata['record_count']
        entry.source_types = metadata.get('source_types', entry.source_types)
        entry.imu_channels = metadata.get('imu_channels', entry.imu_channels)
        entry.time_range = metadata.get('time_range', entry.time_range)
        # 重新统计事件数
        if entry.analysis_db_path:
            entry.event_count = self._count_events_in_analysis_cache(entry.analysis_db_path)
        self._save_entry(entry)
        logger.info(
            f"已刷新缓存条目 {target_id[:8]}...: "
            f"recs={entry.record_count}, evts={entry.event_count}, "
            f"time={entry.time_range[0]:.2f}-{entry.time_range[1]:.2f}"
        )
        return True

    def get_default_id(self) -> Optional[str]:
        """返回默认（最新）缓存的 id"""
        if self._default_id and self._default_id in self._entries:
            return self._default_id
        if self._entries:
            latest = max(self._entries.values(), key=lambda e: e.creation_time)
            self._set_default(latest.id)
            return latest.id
        return None

    def _set_default(self, cache_id: str):
        """设置默认缓存"""
        self._default_id = cache_id
        try:
            with sqlite3.connect(self._index_db) as conn:
                conn.execute("UPDATE cache_index SET is_default = 0")
                conn.execute(
                    "UPDATE cache_index SET is_default = 1 WHERE id = ?",
                    (cache_id,)
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"更新默认缓存失败: {e}")

    def get_default_cache(self) -> Tuple[Any, Any]:
        """获取默认缓存的数据对象"""
        default_id = self.get_default_id()
        if not default_id:
            raise RuntimeError("没有可用的缓存数据集")
        return self.get_cache(default_id)

    @property
    def count(self) -> int:
        return len(self._entries)

    # ── JSON 编解码工具 ────────────────────────────────────────

    @staticmethod
    def _json_encode(obj) -> str:
        import json
        return json.dumps(obj, ensure_ascii=False)

    @staticmethod
    def _json_decode(s: str):
        import json
        if not s or s == '[]':
            return []
        try:
            return json.loads(s)
        except (json.JSONDecodeError, TypeError):
            return []