#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据读取器 - 从配置的数据源中读取数据并推入数据管道
"""

import logging
import time
import threading
import os
import traceback
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

try:
    from core.core.data_processing.signal_filter import get_signal_filter
    FILTER_AVAILABLE = True
except ImportError:
    FILTER_AVAILABLE = False

try:
    from core.core.data_processing.imu_calibration_applier import (
        create_applier_from_source_config,
        apply_calibration_to_cache
    )
    CALIBRATION_AVAILABLE = True
except ImportError:
    CALIBRATION_AVAILABLE = False

logger = logging.getLogger(__name__)


def _open_file_auto_encoding(file_path, mode='r'):
    for enc in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312']:
        try:
            f = open(file_path, mode, encoding=enc)
            f.read(1024)
            f.seek(0)
            return f
        except (UnicodeDecodeError, UnicodeError):
            try:
                f.close()
            except Exception:
                pass
            continue
    return open(file_path, mode, encoding='utf-8', errors='ignore')


@dataclass
class DataSourceSample:
    """数据源样本"""
    timestamp: float
    data: Any
    quality: float = 1.0
    source_id: str = ""


class DataSourceReader:
    """数据读取器"""
    
    def __init__(self, source_id: str, source_config: Any, pipeline_manager: Any):
        """
        初始化数据读取器
        
        Args:
            source_id: 数据源ID
            source_config: 数据源配置
            pipeline_manager: 数据管道管理器
        """
        self.source_id = source_id
        self.source_config = source_config
        self.pipeline_manager = pipeline_manager
        self.data_bridge = None
        self._cache = None
        
        self.is_running = False
        self.reader_thread: Optional[threading.Thread] = None
        
        self.status = "stopped"
        self.data_count = 0
        self.total_records = 0
        self.last_data_time = 0
        self.error_count = 0
        
        self.read_interval = 0.01

        sample_rate = getattr(self.source_config, 'sampling_rate', None)
        if not sample_rate:
            src_type = getattr(self.source_config, 'type', '')
            sample_rate = 125 if src_type.upper() == 'CNAP' else 100
        self._sample_interval = 1.0 / max(1, int(sample_rate))
        self._playback_speed = 10.0
        
        self._file_data_cache = []
        self._file_index = 0
        self._file_loaded = False
        self._normalized_file_path = None
        self._current_file_path = None
        self._file_exhausted = False
        self._on_file_exhausted_callback = None
        self._paused = threading.Event()

        self._base_recording_unix = None
        self._first_record_rel_time = None

        self._effective_source_type = 'unknown'

        # === 校准相关 ===
        self._calibration_applier = None
        self._calibration_applied = False
        self._on_calibration_complete_callback = None

        logger.info(f"数据读取器已创建: {source_id}")
    
    def start(self):
        """启动数据读取"""
        if self.is_running:
            logger.warning(f"数据读取器已在运行: {self.source_id}")
            return
        
        self.is_running = True
        self.status = "running"
        
        # 启动读取线程
        self.reader_thread = threading.Thread(
            target=self._read_loop,
            daemon=True,
            name=f"Reader-{self.source_id}"
        )
        self.reader_thread.start()
        
        logger.info(f"数据读取器已启动: {self.source_id}")
    
    def stop(self):
        """停止数据读取"""
        self.is_running = False
        self.status = "stopped"

        if self._cache:
            try:
                self._cache.flush()
            except Exception as e:
                logger.debug(f"刷新缓存失败: {e}")

        if self.reader_thread:
            self.reader_thread.join(timeout=1.0)

        logger.info(f"数据读取器已停止: {self.source_id}")

    def clear_file_data(self):
        self._file_data_cache.clear()
        self._file_index = 0
        self._file_loaded = False
        self._file_exhausted = False
        self.data_count = 0
        self.total_records = 0
        self._base_recording_unix = None
        self._first_record_rel_time = None

    def set_on_file_exhausted(self, callback):
        """设置文件数据耗尽回调"""
        self._on_file_exhausted_callback = callback

    def set_cache(self, cache):
        """设置磁盘缓存"""
        self._cache = cache

    def resume(self):
        """恢复读取（确认后继续循环）"""
        self._paused.clear()
        self._file_exhausted = False
    
    def _read_loop(self):
        """数据读取循环 — 批量推送以降低信号开销"""
        batch = []
        batch_max = 100
        signal_filter = None
        if FILTER_AVAILABLE:
            try:
                filter_config_dict = getattr(self.source_config, 'signal_filter', None) or {}
                if filter_config_dict.get("enabled"):
                    from core.core.data_processing.signal_filter import FilterConfig, FilterType
                    ft_str = filter_config_dict.get("filter_type", "")
                    ft_map = {
                        "移动平均滤波 (Moving Average)": FilterType.MOVING_AVERAGE,
                        "中值滤波 (Median Filter)": FilterType.MEDIAN,
                        "指数加权滤波 / RC低通 (Exponential)": FilterType.EXPONENTIAL,
                        "高通滤波 (High-Pass)": FilterType.HIGH_PASS,
                        "带通滤波 (Band-Pass)": FilterType.BAND_PASS,
                        "卡尔曼滤波 (Kalman Filter)": FilterType.KALMAN,
                        "巴特沃斯低通滤波 (Butterworth)": FilterType.BUTTERWORTH_LOWPASS,
                        "CFC 1000 — 截止频率 1000 Hz (高频碰撞加速度)": FilterType.CFC_1000,
                        "CFC 600 — 截止频率 600 Hz (头部/胸部碰撞加速度)": FilterType.CFC_600,
                        "CFC 180 — 截止频率 180 Hz (胸部压缩/力传感器)": FilterType.CFC_180,
                        "CFC 60 — 截止频率 60 Hz (安全带力/位移传感器)": FilterType.CFC_60,
                        "CFC 30 — 截止频率 30 Hz (膝部位移/低速碰撞)": FilterType.CFC_30,
                    }
                    ft = ft_map.get(ft_str, FilterType.MOVING_AVERAGE)
                    target_fields = [f.strip() for f in filter_config_dict.get("target_fields", "ax,ay,az").split(",") if f.strip()]
                    fc = FilterConfig(
                        filter_type=ft,
                        enabled=True,
                        window_size=filter_config_dict.get("window_size", 5),
                        alpha=filter_config_dict.get("alpha", 0.3),
                        cutoff_frequency=filter_config_dict.get("cutoff_frequency", 10.0),
                        high_cutoff=filter_config_dict.get("high_cutoff", 50.0),
                        sample_rate=filter_config_dict.get("sample_rate", 100.0),
                        order=filter_config_dict.get("order", 2),
                        process_noise=filter_config_dict.get("process_noise", 0.01),
                        measurement_noise=filter_config_dict.get("measurement_noise", 0.1),
                        target_fields=target_fields,
                    )
                    signal_filter = get_signal_filter(self.source_id, fc)
                    logger.info(f"🔧 已为 {self.source_id} 启用信号滤波: {ft_str}")
            except Exception as e:
                logger.warning(f"初始化信号滤波器失败: {e}")

        while self.is_running:
            if self._paused.is_set():
                time.sleep(0.1)
                continue

            if self.data_count == 0 and not hasattr(self, '_loop_started'):
                self._loop_started = True
                logger.info(f"[{self.source_id}] _read_loop 开始迭代, paused={self._paused.is_set()}, "
                            f"file_loaded={self._file_loaded}, cache_size={len(self._file_data_cache)}, "
                            f"data_bridge={'set' if self.data_bridge else 'None'}")

            sample_interval = self._sample_interval / self._playback_speed
            MIN_SLEEP = 0.025
            if sample_interval < MIN_SLEEP:
                burst_size = max(1, int(MIN_SLEEP / sample_interval))
            else:
                burst_size = 1

            burst_read = 0
            try:
                for _ in range(burst_size):
                    sample = self._read_data()
                    if not sample:
                        if self._file_data_cache and self._file_index >= len(self._file_data_cache):
                            logger.info(f"[{self.source_id}] 文件已读完, data_count={self.data_count}")
                        elif not self._file_data_cache and self._file_loaded:
                            logger.warning(f"[{self.source_id}] 文件已加载但缓存为空!")
                        break

                    self.pipeline_manager.push_data(self.source_id, sample)

                    parsed_record = sample.data.copy()
                    parsed_record['timestamp'] = sample.timestamp
                    parsed_record['source_id'] = sample.source_id
                    parsed_record['_source_type'] = self._effective_source_type

                    if signal_filter is not None:
                        parsed_record = signal_filter.apply(parsed_record)

                    if self.data_bridge:
                        batch.append(parsed_record)
                        if len(batch) >= batch_max:
                            self.data_bridge.feed_parsed_batch(batch)
                            batch.clear()
                    elif self.data_count == 0:
                        logger.warning(f"[{self.source_id}] data_bridge 未设置，无法推送数据")

                    self.data_count += 1
                    self.last_data_time = time.time()
                    burst_read += 1

                if burst_read > 0:
                    sleep_dur = burst_read * sample_interval
                    if self.data_count % 1000 < burst_size:
                        logger.debug(f"[{self.source_id}] 已读 {self.data_count} 条, "
                                    f"速度={self._playback_speed}x, burst={burst_read}, sleep={sleep_dur*1000:.1f}ms")
                    time.sleep(sleep_dur)
                else:
                    if batch and self.data_bridge:
                        self.data_bridge.feed_parsed_batch(batch)
                        batch.clear()
                    time.sleep(0.05)
            except Exception as e:
                logger.error(f"读取数据失败 ({self.source_id}): {e}")
                self.error_count += 1
                self.status = "error"
                time.sleep(0.1)
    
    def _load_file_data(self):
        """从配置文件路径加载数据到缓存（大文件流式加载）"""
        if self._file_loaded:
            return
        self._file_loaded = True
        
        file_path = None
        try:
            conn = getattr(self.source_config, 'connection', None)
            if isinstance(conn, dict):
                file_path = conn.get('file_path', '')
            elif hasattr(conn, 'file_path'):
                file_path = conn.file_path
            if not file_path:
                logger.debug(f"数据源 {self.source_id} 无文件路径配置")
                return
            if not Path(file_path).exists():
                logger.warning(f"数据文件不存在: {file_path}")
                return
        except Exception as e:
            logger.warning(f"获取文件路径失败: {e}")
            return

        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > 500:
            logger.warning(f"大文件检测: {file_path} ({file_size_mb:.1f}MB)，将使用流式加载")
        elif file_size_mb > 100:
            logger.info(f"较大文件: {file_path} ({file_size_mb:.1f}MB)")

        source_type = getattr(self.source_config, 'type', 'unknown')
        parsing = getattr(self.source_config, 'parsing', {})
        parser_type = parsing.get('type', '') if isinstance(parsing, dict) else ''
        if parser_type and parser_type.upper() != 'GENERIC':
            effective_type = parser_type
        else:
            effective_type = source_type
        
        try:
            if effective_type.upper() == 'CNAP':
                self._effective_source_type = 'cnap'
                self._current_file_path = file_path
                if file_size_mb > 200:
                    self._parse_cnap_file_streaming(file_path)
                else:
                    with _open_file_auto_encoding(file_path) as f:
                        content = f.read()
                    self._parse_cnap_file(content)
            elif effective_type.upper() == 'CAN':
                self._current_file_path = file_path
                self._parse_can_file(None)
                self._effective_source_type = self._detect_can_format()
            elif effective_type.upper() == 'IMU':
                self._effective_source_type = 'imu_standalone'
                if file_size_mb > 200:
                    self._parse_imu_file_streaming(file_path)
                else:
                    with _open_file_auto_encoding(file_path) as f:
                        content = f.read()
                    self._parse_imu_file(content)
            else:
                self._effective_source_type = effective_type.lower()
                if file_size_mb > 200:
                    self._parse_file_lines_streaming(file_path)
                else:
                    self._parse_file_lines(file_path)
            
            cache_size = len(self._file_data_cache)
            logger.info(f"从文件加载了 {cache_size} 条 {effective_type} 数据: {file_path}")
            self.total_records = cache_size

            if cache_size > 100000:
                logger.info(f"大数据集: {cache_size} 条记录, 估算内存 ~{cache_size * 0.5 / 1024:.0f}MB")

            # === 应用 IMU 校准 ===
            if CALIBRATION_AVAILABLE and self._file_data_cache:
                try:
                    self._calibration_applier = create_applier_from_source_config(self.source_config)
                    if self._calibration_applier.is_enabled():
                        logger.info(f"开始应用 IMU 校准到 {len(self._file_data_cache)} 条数据")
                        self._file_data_cache = apply_calibration_to_cache(
                            self._file_data_cache,
                            self._calibration_applier.calibration_config
                        )
                        logger.info("IMU 校准应用完成")
                    else:
                        logger.info("IMU 校准未启用，跳过")
                    self._calibration_applied = self._calibration_applier.is_enabled()
                except Exception as e:
                    logger.error(f"应用 IMU 校准失败: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    self._calibration_applied = False
            else:
                self._calibration_applied = False

            if self._cache and self._file_data_cache:
                self._start_async_cache_writer()
        except MemoryError:
            logger.error(f"内存不足，无法加载文件: {file_path} ({file_size_mb:.1f}MB)")
            self._file_data_cache = self._file_data_cache[:100000]
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")

    def _start_async_cache_writer(self, on_complete=None):
        """启动后台线程，分批异步写入缓存（不阻塞数据读取）
        使用非daemon线程确保写入完成后再退出
        
        Args:
            on_complete: 写入完成后的回调函数，签名为 on_complete(source_type)
        """
        cache = self._cache
        data = self._file_data_cache
        source_type = self._effective_source_type
        source_id = self.source_id

        def _writer():
            total = len(data)
            batch_size = 10000
            written = 0
            batch_count = 0
            total_batches = (total + batch_size - 1) // batch_size
            start_time = time.time()
            for offset in range(0, total, batch_size):
                end = min(offset + batch_size, total)
                batch = data[offset:end]
                for rec in batch:
                    rec['_source_type'] = source_type
                try:
                    cache.write_batch(batch)
                    written += len(batch)
                    batch_count += 1
                    if batch_count % 5 == 0 or batch_count == total_batches:
                        elapsed = time.time() - start_time
                        pct = written / total * 100
                        logger.info(f"[异步缓存写入] {source_id} 进度: {written}/{total} ({pct:.1f}%), "
                                    f"批次 {batch_count}/{total_batches}, 耗时 {elapsed:.1f}s")
                except Exception as e:
                    logger.error(f"[异步缓存写入] 批次失败: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            try:
                cache.flush()
            except Exception:
                pass
            elapsed = time.time() - start_time
            logger.info(f"[异步缓存写入] 完成: {written} 条 {source_type} 数据已写入缓存, 总耗时 {elapsed:.1f}s")
            
            if on_complete:
                try:
                    on_complete(source_type)
                except Exception as e:
                    logger.error(f"[异步缓存写入] 完成回调失败: {e}")

        t = threading.Thread(target=_writer, daemon=False,
                             name=f"async-cache-{source_id}")
        t.start()
        logger.info(f"[{source_id}] 异步缓存写入已启动, 共 {len(data)} 条, 预计 {len(data)//2000} 批次")

    def _parse_cnap_file(self, content):
        import importlib.util
        import re

        project_root = Path(__file__).parent.parent.parent.parent.parent
        parser_path = project_root / "core" / "core" / "data_processing" / "cnap_parser_autogen.py"

        parsed_ok = False
        try:
            spec = importlib.util.spec_from_file_location("_cnap_parser", str(parser_path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            parser = mod.cnap_parser_CustomParser()
            df = parser.parse_file(self._current_file_path)

            wave_count = 0
            beat_count = 0
            for _, row in df.iterrows():
                rec = {}
                for k, v in row.items():
                    if pd.notna(v):
                        rec[k] = v
                if rec.get('cnap_type') in ('WAVE', 'BEATS'):
                    parsed_ok = True
                self._file_data_cache.append(rec)
                if rec.get('cnap_type') == 'WAVE':
                    wave_count += 1
                elif rec.get('cnap_type') == 'BEATS':
                    beat_count += 1

            if parsed_ok:
                logger.info(f"CNAP 数据解析完成: WAVE={wave_count}, BEATS={beat_count}, "
                            f"共 {len(self._file_data_cache)} 条")
            else:
                logger.warning("cnap_parser_autogen 未产出有效CNAP记录，回退到内置解析")
                self._file_data_cache.clear()
                raise ValueError("autogen parser produced no valid CNAP records")
        except Exception as e:
            if not parsed_ok:
                logger.warning(f"cnap_parser_autogen 失败 ({e})，使用内置正则解析")

                _BEATS_PARAM_MAPPING = [
                    ('Systolic_BP', 0), ('Diastolic_BP', 1), ('Heart_Rate', 2),
                    ('Mean_Arterial_Pressure', 3), ('Pulse_Pressure', 4),
                    ('Heart_Rate_Variability', 5), ('Mean_Pulse_Pressure', 6),
                    ('Stroke_Volume', 7), ('Vascular_Resistance', 8),
                    ('PPV', 9), ('SVV', 10), ('Ejection_Fraction', 11),
                ]

                wave_pattern = re.compile(r"Data:\s*b'%WAVE%([\d.]+):\s*([\d.]+)'")
                beats_pattern = re.compile(r"Data:\s*b'%BEATS%([\d.]+):\s*([^']+)'")

                wave_records = []
                for match in wave_pattern.finditer(content):
                    wave_records.append({
                        'cnap_type': 'WAVE',
                        'wave_t': float(match.group(1)),
                        'pressure': float(match.group(2)),
                    })

                beats_records = []
                for match in beats_pattern.finditer(content):
                    params_str = match.group(2)
                    clean = params_str.strip().rstrip('\\n').rstrip(';').strip()
                    parts = [p.strip() for p in clean.split(';')]
                    rec = {'cnap_type': 'BEATS', 'beat_t': float(match.group(1))}
                    for name, idx in _BEATS_PARAM_MAPPING:
                        try:
                            v = float(parts[idx])
                            rec[name] = None if v in (-1.0, -1) else v
                        except (IndexError, ValueError):
                            rec[name] = None
                    beats_records.append(rec)

                wi = 0
                bi = 0
                while wi < len(wave_records) and bi < len(beats_records):
                    if wave_records[wi]['wave_t'] <= beats_records[bi]['beat_t']:
                        self._file_data_cache.append(wave_records[wi])
                        wi += 1
                    else:
                        self._file_data_cache.append(beats_records[bi])
                        bi += 1
                while wi < len(wave_records):
                    self._file_data_cache.append(wave_records[wi])
                    wi += 1
                while bi < len(beats_records):
                    self._file_data_cache.append(beats_records[bi])
                    bi += 1

                logger.info(f"CNAP 回退解析完成: WAVE={len(wave_records)}, BEATS={len(beats_records)}, "
                            f"共 {len(self._file_data_cache)} 条（已按时间戳交错排序）")

    def _parse_imu_file(self, content):
        from core.core.data_processing.data_parser import IMUDataParser

        try:
            parser = IMUDataParser()
            results = parser.parse_content(content)
            for rec in results:
                self._file_data_cache.append(rec)
            logger.info(f"IMU 解析完成: {len(results)} 个数据包, ax=({results[0].get('ax',0):.4f}~{results[-1].get('ax',0):.4f})")

            self._run_imu_normalization()

        except Exception as e:
            logger.warning(f"IMUDataParser 加载失败 ({e})，回退到内置解析")
            import re
            for match in re.finditer(
                r'([\d.-]+),([\d.-]+),([\d.-]+),([\d.-]+),[\d.]+BB[A-F0-9]{6},([\d.-]+),([\d.-]+),([\d.-]+)',
                content
            ):
                try:
                    self._file_data_cache.append({
                        'ax': float(match.group(5)),
                        'ay': float(match.group(6)),
                        'az': float(match.group(7)),
                    })
                except (ValueError, IndexError):
                    continue

    def _run_imu_normalization(self):
        try:
            from core.core.data_processing.data_normalizer import DataNormalizer
            normalizer = DataNormalizer()
            filepath, written, stats = normalizer.normalize_batch_and_save(
                self._file_data_cache
            )
            if filepath:
                self._normalized_file_path = filepath
                logger.info(
                    f"IMU 标准化完成: {written} 条 → {filepath}, "
                    f"12字段={stats.get('twelve_field', 0)}, "
                    f"8字段={stats.get('eight_field', 0)}, "
                    f"估算gz={stats.get('estimated_gz', 0)}"
                )
        except Exception as e:
            logger.warning(f"IMU 标准化失败: {e}")

    def _parse_can_file(self, content):
        # 检查是否是车厢地板IMU专用解析模式
        use_floor_imu = False
        if hasattr(self, 'source_config'):
            parsing = getattr(self.source_config, 'parsing', {})
            use_floor_imu = parsing.get('use_floor_imu_parser', False) if isinstance(parsing, dict) else False
        
        if use_floor_imu:
            self._parse_can_floor_imu()
        else:
            # 使用原来的CANFullParser
            self._parse_can_original()
    
    def _parse_can_floor_imu(self):
        """全通道10IMU解析 - 双流数据分发
        
        硬编码策略：使用 ch4 座椅底部 IMU (IMU7/IMU8) 作为可视化与实时行为监控数据源。
        自动比较 IMU7(实验组) 与 IMU8(对照组) 的数据质量，选取质量更优者。
        """
        try:
            from core.core.data_processing.floor_imu_parser import (
                parse_all_channels, 
                IMU_NAME_MAP
            )
            
            logger.info("=== 启用全通道10IMU解析器 ===")
            
            HARDCODED_IMU_CANDIDATES = ['IMU7_座椅底部-1', 'IMU8_座椅底部-2']
            
            all_channel_data, vehicle_data = parse_all_channels(self._current_file_path)

            stats = {}
            for name, records in all_channel_data.items():
                stats[name] = len(records)
            logger.info(f"[全通道解析] 各IMU数据量: {stats}")

            def _quality_score(records):
                if not records:
                    return 0, 0.0
                valid = 0
                values = []
                for r in records:
                    ax = r.get('ax')
                    ay = r.get('ay')
                    az = r.get('az')
                    gx = r.get('gx')
                    gy = r.get('gy')
                    gz = r.get('gz')
                    if all(v is not None for v in (ax, ay, az, gx, gy, gz)):
                        valid += 1
                        values.append(abs(ax) + abs(ay) + abs(az))
                if not values:
                    return valid, 0.0
                variance = sum((v - sum(values)/len(values))**2 for v in values) / len(values)
                return valid, variance

            target_imu_name = None
            candidates_available = [n for n in HARDCODED_IMU_CANDIDATES if n in all_channel_data]
            if len(candidates_available) == 1:
                target_imu_name = candidates_available[0]
                logger.info(f"[硬编码ch4] 仅 {target_imu_name} 可用, 数据量: {len(all_channel_data[target_imu_name])}")
            elif len(candidates_available) == 2:
                q7 = _quality_score(all_channel_data['IMU7_座椅底部-1'])
                q8 = _quality_score(all_channel_data['IMU8_座椅底部-2'])
                logger.info(f"[硬编码ch4] IMU7(实验组): valid={q7[0]}, variance={q7[1]:.4f}")
                logger.info(f"[硬编码ch4] IMU8(对照组): valid={q8[0]}, variance={q8[1]:.4f}")

                if q7[0] > q8[0]:
                    target_imu_name = 'IMU7_座椅底部-1'
                elif q8[0] > q7[0]:
                    target_imu_name = 'IMU8_座椅底部-2'
                elif q7[1] >= q8[1]:
                    target_imu_name = 'IMU7_座椅底部-1'
                else:
                    target_imu_name = 'IMU8_座椅底部-2'

                logger.info(f"[硬编码ch4] 选中: {target_imu_name}, 数据量: {len(all_channel_data[target_imu_name])}")
            else:
                logger.warning("[硬编码ch4] IMU7/IMU8 均不可用，回退到自动选择")
                sorted_imus = sorted(stats.items(), key=lambda x: x[1], reverse=True)
                if sorted_imus:
                    target_imu_name = sorted_imus[0][0]
                    logger.info(f"[硬编码ch4] 回退选择: {target_imu_name}, 数据量: {len(all_channel_data[target_imu_name])}")

            self._file_data_cache = []

            if target_imu_name and target_imu_name in all_channel_data:
                vis_records = all_channel_data[target_imu_name]
                for rec in vis_records:
                    rec_copy = dict(rec)
                    rec_copy['_source_id'] = f"{self.source_id}_visualization"
                    rec_copy['_imu_name'] = target_imu_name
                    rec_copy['_is_visualization'] = True
                    self._file_data_cache.append(rec_copy)
                logger.info(f"[硬编码ch4] 可视化数据源: {target_imu_name}, {len(vis_records)} 条已就绪")

            for imu_name, records in all_channel_data.items():
                for rec in records:
                    rec_copy = dict(rec)
                    rec_copy['_source_id'] = f"{self.source_id}_{imu_name}"
                    rec_copy['_imu_name'] = imu_name
                    self._file_data_cache.append(rec_copy)
            
            logger.info(f"[全通道解析] 总计 {len(self._file_data_cache)} 条记录，按时间戳排序中...")
            self._file_data_cache.sort(key=lambda r: r.get('timestamp', 0))
            logger.info(f"[全通道解析] 时间戳排序完成，时间范围: "
                        f"{self._file_data_cache[0].get('timestamp', 0):.3f} ~ "
                        f"{self._file_data_cache[-1].get('timestamp', 0):.3f}")
            
            logger.info(f"=== 全通道10IMU解析完成: 总计 {len(self._file_data_cache)} 条记录 ===")
            if self._file_data_cache:
                sample = self._file_data_cache[0]
                logger.info(f"  首条记录: ts={sample.get('timestamp'):.3f}, ax={sample.get('ax'):.3f}, ay={sample.get('ay'):.3f}, az={sample.get('az'):.3f}, imu={sample.get('_imu_name', 'unknown')}")
            
        except Exception as e:
            logger.error(f"全通道10IMU解析器失败 ({e})，回退到原始解析器")
            import traceback
            logger.error(traceback.format_exc())
            self._parse_can_original()
    
    def _parse_can_original(self):
        """使用原来的CANFullParser解析"""
        from core.core.data_processing.can_parser_v2 import CANFullParser
        try:
            axis_cfg = getattr(self.source_config, 'axis_correction', None)
            parser = CANFullParser(axis_correction_config=axis_cfg)
            try:
                import glob as _glob
                drive_dir = os.path.dirname(self._current_file_path)
                candidates = (
                    _glob.glob(drive_dir + '/*park*') +
                    _glob.glob(drive_dir + '/*Park*') +
                    _glob.glob(drive_dir + '/*PARK*') +
                    _glob.glob(drive_dir + '/*驻车*')
                )
                candidates = [c for c in candidates
                              if not os.path.basename(c).startswith('parsed_')]
                if candidates:
                    parser.calibrate(candidates[0])
                    logger.info(f"使用驻车标定文件: {candidates[0]}")
                else:
                    # 使用文件开头的驻车数据进行自校准
                    logger.info("未找到独立驻车文件，使用文件开头数据进行自校准...")
                    parser.auto_calibrate_from_file(self._current_file_path)
            except Exception as e:
                logger.warning(f"校准失败 ({e})，使用默认校准")
                parser._set_default_calibration()
            for record in parser.parse_file_long_format(self._current_file_path):
                self._file_data_cache.append(record)
            logger.info(f"CAN全通道10IMU解析完成: {len(self._file_data_cache)} 条记录")
            if self._file_data_cache:
                first_keys = list(self._file_data_cache[0].keys())[:30]
                logger.info(f"  首条CAN记录字段({len(first_keys)}): {first_keys}")
                imu_names = set(r.get('_imu_name', 'unknown') for r in self._file_data_cache[:1000])
                channel_counts = {}
                for r in self._file_data_cache:
                    imu = r.get('_imu_name', 'unknown')
                    channel_counts[imu] = channel_counts.get(imu, 0) + 1
                logger.info(f"  各IMU数据量: {channel_counts}")
                logger.info(f"  检测到 {len(imu_names)} 路独立IMU: {sorted(imu_names)}")
        except Exception as e:
            logger.warning(f"CANFullParser 加载失败 ({e})，回退到原始行读取")
            try:
                with _open_file_auto_encoding(self._current_file_path) as f:
                    content = f.read()
            except Exception:
                content = ""
            for line in content.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                self._file_data_cache.append({'raw': line})

    def _detect_can_format(self) -> str:
        if not self._file_data_cache:
            return 'can_wide'
        sample = self._file_data_cache[0]
        if any(k in sample for k in ('Ax_m_s2', 'Gx_dps', 'imu_name', '_imu_name')):
            return 'can_long'
        if all(k in sample for k in ('ax', 'ay', 'az')):
            return 'can_long'
        if any(k.startswith('ch') and '_ax' in k for k in sample):
            return 'can_wide'
        if 'raw' in sample:
            raw_line = str(sample.get('raw', ''))
            if any(k in raw_line for k in ('Ax_m_s2', 'Gx_dps', 'imu_name', '_imu_name')):
                return 'can_long'
            return 'can_wide'
        return 'can_wide'

    def _parse_file_lines(self, file_path):
        parser = self._get_configured_parser()
        if parser:
            try:
                with _open_file_auto_encoding(file_path) as f:
                    content = f.read()
                results = parser.parse_content(content)
                for rec in results:
                    self._file_data_cache.append(rec)
                logger.info(f"使用配置解析器解析完成: {len(results)} 条")
                return
            except Exception as e:
                logger.warning(f"配置解析器失败 ({e})，回退到原始行读取")

        with _open_file_auto_encoding(file_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                self._file_data_cache.append({'raw': line})

    def _parse_file_lines_streaming(self, file_path):
        """大文件流式行读取（逐行处理，避免全量加载到内存）"""
        parser = self._get_configured_parser()
        chunk_size = 50000
        chunk = []
        total = 0

        with _open_file_auto_encoding(file_path) as f:
            if parser:
                for line in f:
                    chunk.append(line)
                    if len(chunk) >= chunk_size:
                        content = ''.join(chunk)
                        try:
                            results = parser.parse_content(content)
                            for rec in results:
                                self._file_data_cache.append(rec)
                        except Exception as e:
                            logger.warning(f"流式解析块失败: {e}")
                        total += len(chunk)
                        chunk = []
                        if total % 200000 == 0:
                            logger.info(f"流式加载进度: {total} 行")
                if chunk:
                    content = ''.join(chunk)
                    try:
                        results = parser.parse_content(content)
                        for rec in results:
                            self._file_data_cache.append(rec)
                    except Exception as e:
                        logger.warning(f"流式解析最后块失败: {e}")
            else:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    self._file_data_cache.append({'raw': line})
                    total += 1
                    if total % 200000 == 0:
                        logger.info(f"流式加载进度: {total} 行")

        logger.info(f"流式加载完成: {len(self._file_data_cache)} 条记录")

    def _parse_cnap_file_streaming(self, file_path):
        """CNAP大文件流式解析（使用autogen解析器，分块处理DataFrame）"""
        import importlib.util
        import re

        project_root = Path(__file__).parent.parent.parent.parent.parent
        parser_path = project_root / "core" / "core" / "data_processing" / "cnap_parser_autogen.py"

        try:
            spec = importlib.util.spec_from_file_location("_cnap_parser", str(parser_path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            parser = mod.cnap_parser_CustomParser()
            df = parser.parse_file(file_path)

            chunk_size = 10000
            wave_count = 0
            beat_count = 0
            for start in range(0, len(df), chunk_size):
                end = min(start + chunk_size, len(df))
                chunk_df = df.iloc[start:end]
                for _, row in chunk_df.iterrows():
                    rec = {}
                    for k, v in row.items():
                        if pd.notna(v):
                            rec[k] = v
                    self._file_data_cache.append(rec)
                    if rec.get('cnap_type') == 'WAVE':
                        wave_count += 1
                    elif rec.get('cnap_type') == 'BEATS':
                        beat_count += 1
                if start + chunk_size < len(df):
                    logger.info(f"CNAP流式加载进度: {end}/{len(df)} 条")

            logger.info(f"CNAP流式加载完成: WAVE={wave_count}, BEATS={beat_count}, "
                        f"共 {len(self._file_data_cache)} 条")
        except Exception as e:
            logger.warning(f"CNAP autogen解析失败 ({e})，使用内置正则解析")
            self._parse_cnap_fallback_streaming(file_path)

    def _parse_cnap_fallback_streaming(self, file_path):
        """CNAP大文件回退正则流式解析"""
        import re

        _BEATS_PARAM_MAPPING = [
            ('Systolic_BP', 0), ('Diastolic_BP', 1), ('Heart_Rate', 2),
            ('Mean_Arterial_Pressure', 3), ('Pulse_Pressure', 4),
            ('Heart_Rate_Variability', 5), ('Mean_Pulse_Pressure', 6),
            ('Stroke_Volume', 7), ('Vascular_Resistance', 8),
            ('PPV', 9), ('SVV', 10), ('Ejection_Fraction', 11),
        ]

        wave_pattern = re.compile(r"Data:\s*b'%WAVE%([\d.]+):\s*([\d.]+)'")
        beats_pattern = re.compile(r"Data:\s*b'%BEATS%([\d.]+):\s*([\d,]+)'")

        wave_records = []
        beats_records = []
        total_lines = 0

        with _open_file_auto_encoding(file_path) as f:
            for line in f:
                total_lines += 1
                wave_match = wave_pattern.search(line)
                if wave_match:
                    wave_records.append({
                        'cnap_type': 'WAVE',
                        'wave_t': float(wave_match.group(1)),
                        'wave_v': float(wave_match.group(2)),
                    })
                    continue

                beats_match = beats_pattern.search(line)
                if beats_match:
                    beat_t = float(beats_match.group(1))
                    values = beats_match.group(2).split(',')
                    rec = {'cnap_type': 'BEATS', 'beat_t': beat_t}
                    for param_name, idx in _BEATS_PARAM_MAPPING:
                        if idx < len(values):
                            try:
                                rec[param_name] = float(values[idx])
                            except ValueError:
                                rec[param_name] = values[idx]
                    beats_records.append(rec)

                if total_lines % 200000 == 0:
                    logger.info(f"CNAP回退流式加载进度: {total_lines} 行, "
                                f"WAVE={len(wave_records)}, BEATS={len(beats_records)}")

        wi = bi = 0
        while wi < len(wave_records) or bi < len(beats_records):
            if wi >= len(wave_records):
                self._file_data_cache.append(beats_records[bi])
                bi += 1
            elif bi >= len(beats_records):
                self._file_data_cache.append(wave_records[wi])
                wi += 1
            elif wave_records[wi]['wave_t'] <= beats_records[bi]['beat_t']:
                self._file_data_cache.append(wave_records[wi])
                wi += 1
            else:
                self._file_data_cache.append(beats_records[bi])
                bi += 1

        logger.info(f"CNAP回退流式解析完成: WAVE={len(wave_records)}, BEATS={len(beats_records)}, "
                    f"共 {len(self._file_data_cache)} 条")

    def _parse_imu_file_streaming(self, file_path):
        """IMU大文件流式解析"""
        from core.core.data_processing.data_parser import IMUDataParser
        parser = IMUDataParser()
        chunk_size = 50000
        chunk = []
        total = 0

        with _open_file_auto_encoding(file_path) as f:
            for line in f:
                chunk.append(line)
                if len(chunk) >= chunk_size:
                    content = ''.join(chunk)
                    try:
                        results = parser.parse_content(content)
                        for rec in results:
                            self._file_data_cache.append(rec)
                    except Exception as e:
                        logger.warning(f"IMU流式解析块失败: {e}")
                    total += len(chunk)
                    chunk = []
                    if total % 200000 == 0:
                        logger.info(f"IMU流式加载进度: {total} 行")
            if chunk:
                content = ''.join(chunk)
                try:
                    results = parser.parse_content(content)
                    for rec in results:
                        self._file_data_cache.append(rec)
                except Exception as e:
                    logger.warning(f"IMU流式解析最后块失败: {e}")

        logger.info(f"IMU流式加载完成: {len(self._file_data_cache)} 条记录")
        self._run_imu_normalization()

    def _get_configured_parser(self):
        try:
            parsing_config = getattr(self.source_config, 'parsing', None)
            if not parsing_config:
                return None
            parser_module_name = parsing_config.get('parser_module', '') if isinstance(parsing_config, dict) else getattr(parsing_config, 'parser_module', '')
            parser_class_name = parsing_config.get('parser_class', '') if isinstance(parsing_config, dict) else getattr(parsing_config, 'parser_class', '')
            if not parser_module_name or not parser_class_name:
                return None
            import importlib
            module = importlib.import_module(parser_module_name)
            parser_class = getattr(module, parser_class_name, None)
            if parser_class:
                return parser_class()
        except Exception as e:
            logger.debug(f"获取配置解析器失败: {e}")
        return None

    def _extract_base_time(self) -> float:
        if self._current_file_path:
            import re
            basename = os.path.basename(self._current_file_path)
            m = re.search(r'(\d{4})_(\d{2})_(\d{2})_(\d{2})(\d{2})(\d{2})', basename)
            if m:
                y, mo, d, h, mi, s = map(int, m.groups())
                dt = datetime(y, mo, d, h, mi, s)
                return dt.timestamp()
        return time.time()

    def _read_data(self) -> Optional[DataSourceSample]:
        try:
            self._load_file_data()

            if self._file_data_cache:
                if self._file_index >= len(self._file_data_cache):
                    if not self._file_exhausted:
                        self._file_exhausted = True
                        self._paused.set()
                        logger.info(f"[{self.source_id}] 文件耗尽，回调={'已设置' if self._on_file_exhausted_callback else '未设置'}")
                        if self._on_file_exhausted_callback:
                            try:
                                self._on_file_exhausted_callback(self.source_id, self.data_count)
                            except Exception as e:
                                logger.error(f"文件耗尽回调失败: {e}")
                    return None
                data = self._file_data_cache[self._file_index]
                self._file_index += 1

                if self._base_recording_unix is None:
                    self._base_recording_unix = True

                rel_time = data.get('timestamp', data.get('wave_t', data.get('beat_t', None)))
                if rel_time is not None and isinstance(rel_time, (int, float)):
                    if self._first_record_rel_time is None:
                        self._first_record_rel_time = rel_time
                    timestamp = rel_time - self._first_record_rel_time
                else:
                    if self._first_record_rel_time is None:
                        self._first_record_rel_time = time.time()
                    timestamp = time.time() - self._first_record_rel_time

                quality = 1.0
                source_id = self.source_id
                return DataSourceSample(
                    timestamp=timestamp,
                    data=data,
                    quality=quality,
                    source_id=source_id
                )

            return None

        except Exception as e:
            logger.error(f"读取数据失败 ({self.source_id}): {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """获取读取器状态"""
        return {
            'source_id': self.source_id,
            'status': self.status,
            'data_count': self.data_count,
            'total_records': self.total_records,
            'last_data_time': self.last_data_time,
            'error_count': self.error_count,
            'is_running': self.is_running,
            'calibration_applied': self._calibration_applied
        }

    def pause_reading(self):
        """
        暂停数据读取（用于校准前）
        """
        logger.info(f"[{self.source_id}] 暂停数据读取")
        self._paused.set()
        self.status = "paused"

    def resume_reading(self):
        """
        恢复数据读取
        """
        logger.info(f"[{self.source_id}] 恢复数据读取")
        self._paused.clear()
        self.status = "running"

    def set_on_calibration_complete(self, callback):
        """
        设置校准完成回调
        """
        self._on_calibration_complete_callback = callback

    def apply_new_calibration(self, calibration_config: Dict[str, Any]) -> bool:
        """
        应用新校准（完整流程：暂停→更新缓存→重写缓存→重启）

        Args:
            calibration_config: 新的校准配置

        Returns:
            是否成功
        """
        if not CALIBRATION_AVAILABLE:
            logger.warning("校准模块不可用")
            return False

        try:
            logger.info(f"[{self.source_id}] 开始应用新校准")
            start_time = time.time()

            # 1. 暂停读取
            self.pause_reading()

            # 2. 重新解析原始数据（得到未校准数据）
            logger.info(f"[{self.source_id}] 重新解析原始数据")
            self._file_loaded = False
            self._file_data_cache = []
            self._load_file_data()
            if not self._file_data_cache:
                logger.error("重新解析数据失败")
                return False

            # 3. 应用新校准
            logger.info(f"[{self.source_id}] 应用新校准配置")
            self._calibration_applier = create_applier_from_source_config({
                'imu_calibration': calibration_config
            })
            self._calibration_applier.calibration_config = calibration_config
            self._calibration_applier.enabled = calibration_config.get('enabled', False)
            self._calibration_applier.parameters = calibration_config.get('parameters', {})

            if self._calibration_applier.is_enabled():
                logger.info(f"开始应用新校准到 {len(self._file_data_cache)} 条数据")
                self._file_data_cache = apply_calibration_to_cache(
                    self._file_data_cache,
                    calibration_config
                )
                self._calibration_applied = True
                logger.info("新校准应用完成")
            else:
                logger.info("新校准未启用")
                self._calibration_applied = False

            # 4. 清空并重新写入缓存
            if self._cache:
                logger.info(f"[{self.source_id}] 清空并重新写入缓存")
                try:
                    self._cache.clear()
                except Exception as e:
                    logger.warning(f"清空缓存失败（可能不支持）: {e}")

                self._start_async_cache_writer(
                    on_complete=lambda source_type: self._on_calibration_cache_write_complete()
                )

            # 5. 重置读取位置
            self._file_index = 0
            self.data_count = 0

            elapsed = time.time() - start_time
            logger.info(f"[{self.source_id}] 新校准应用成功，耗时 {elapsed:.1f}s")
            return True

        except Exception as e:
            logger.error(f"应用新校准失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.status = "error"
            return False

    def _on_calibration_cache_write_complete(self):
        """
        校准后缓存写入完成回调
        """
        logger.info(f"[{self.source_id}] 校准后缓存写入完成")
        # 恢复读取
        self.resume_reading()
        # 通知回调
        if self._on_calibration_complete_callback:
            try:
                self._on_calibration_complete_callback(self.source_id)
            except Exception as e:
                logger.error(f"校准完成回调失败: {e}")


class DataReaderManager:
    """数据读取器管理器"""
    
    def __init__(self, config_manager: Any, pipeline_manager: Any):
        """
        初始化管理器
        
        Args:
            config_manager: 配置管理器
            pipeline_manager: 数据管道管理器
        """
        self.config_manager = config_manager
        self.pipeline_manager = pipeline_manager
        self.data_bridge = None
        self._cache = None
        
        self.readers: Dict[str, DataSourceReader] = {}
        self.is_active = False
        self._started_reader_ids: set = set()  # 追踪实际已启动的 reader
        
        logger.info("数据读取器管理器已创建")
    
    def start_all_readers(self):
        """启动所有启用的数据源读取器"""
        try:
            data_sources = getattr(self.config_manager, 'data_sources', {})
            
            for source_id, source_config in data_sources.items():
                if getattr(source_config, 'enabled', False):
                    self.start_reader(source_id)
            
            self.is_active = True
            logger.info(f"已启动 {len(self.readers)} 个数据读取器")
            
        except Exception as e:
            logger.error(f"启动数据读取器失败: {e}")
    
    def start_selected_readers(self, selected_ids: list):
        """启动指定ID的数据源读取器"""
        try:
            data_sources = getattr(self.config_manager, 'data_sources', {})
            
            # ── 确保 DataBridge 运行以处理新数据源 ──
            if self.data_bridge and not self.data_bridge.is_running:
                try:
                    self.data_bridge.start_processing()
                    logger.info("自动重启 DataBridge 以处理新数据源")
                except Exception as e:
                    logger.warning(f"DataBridge 重启失败: {e}")
            
            for source_id in selected_ids:
                if source_id in data_sources:
                    self.start_reader(source_id)
            
            self.is_active = True
            logger.info(f"已启动 {len(selected_ids)} 个选中的数据读取器")
            
        except Exception as e:
            logger.error(f"启动选中数据读取器失败: {e}")
    
    def set_data_bridge(self, data_bridge):
        """设置数据桥接器"""
        self.data_bridge = data_bridge
        for reader in self.readers.values():
            reader.data_bridge = data_bridge
        logger.info(f"DataBridge 已设置给数据读取器管理器")

    def set_cache(self, cache):
        """设置磁盘缓存（传播到所有读取器）"""
        self._cache = cache
        for reader in self.readers.values():
            reader.set_cache(cache)
        logger.info("MultiSourceCache 已设置给数据读取器管理器")

    def get_cache(self):
        """获取磁盘缓存"""
        return self._cache

    def set_file_exhausted_callback(self, callback):
        """设置文件数据耗尽回调（传播到所有读取器）"""
        self._file_exhausted_callback = callback
        for reader in self.readers.values():
            reader.set_on_file_exhausted(callback)
    
    def start_reader(self, source_id: str):
        """启动指定数据源的读取器"""
        try:
            if source_id in self.readers:
                reader = self.readers[source_id]
                self._started_reader_ids.add(source_id)
                if reader.is_running:
                    reader.resume()
                else:
                    reader.start()
                return
            
            # 获取数据源配置
            data_sources = getattr(self.config_manager, 'data_sources', {})
            if source_id not in data_sources:
                logger.warning(f"数据源不存在: {source_id}")
                return
            
            source_config = data_sources[source_id]
            
            # 创建并启动读取器
            reader = DataSourceReader(source_id, source_config, self.pipeline_manager)
            if self.data_bridge:
                reader.data_bridge = self.data_bridge
            if self._cache:
                reader.set_cache(self._cache)
            if hasattr(self, '_file_exhausted_callback') and self._file_exhausted_callback:
                reader.set_on_file_exhausted(self._file_exhausted_callback)
            self.readers[source_id] = reader
            reader.start()
            self._started_reader_ids.add(source_id)
            
            logger.info(f"数据读取器已启动: {source_id}")
            
        except Exception as e:
            logger.error(f"启动数据读取器失败 ({source_id}): {e}")
    
    def stop_reader(self, source_id: str):
        """停止指定数据源的读取器"""
        if source_id in self.readers:
            self.readers[source_id].stop()

    def resume_reader(self, source_id: str):
        """恢复指定数据源的读取器"""
        if source_id in self.readers:
            self.readers[source_id].resume()
            logger.info(f"数据读取器已恢复: {source_id}")

    def set_playback_speed(self, speed: float):
        """设置所有读取器的播放速度倍率"""
        for reader in self.readers.values():
            reader._playback_speed = max(0.1, min(50.0, speed))
        logger.info(f"播放速度已设置为: {speed}x")
    
    def stop_all_readers(self):
        """停止所有数据读取器"""
        for source_id, reader in self.readers.items():
            reader.stop()
        
        self.is_active = False
        logger.info("所有数据读取器已停止")

    def clear_all_reader_data(self):
        """清除所有读取器的文件缓存数据"""
        for source_id, reader in self.readers.items():
            reader.stop()
            reader.clear_file_data()
        self.readers.clear()
        self.is_active = False
        logger.info("所有读取器数据已清除")
    
    def refresh_readers(self):
        """刷新读取器列表（数据源变化时调用，不自动启动）"""
        try:
            data_sources = getattr(self.config_manager, 'data_sources', {})
            current_ids = set(data_sources.keys())
            existing_ids = set(self.readers.keys())
            
            for source_id in existing_ids - current_ids:
                self.readers[source_id].stop()
                del self.readers[source_id]
                logger.info(f"已移除数据读取器: {source_id}")
            
            for source_id in current_ids - existing_ids:
                source_config = data_sources[source_id]
                reader = DataSourceReader(source_id, source_config, self.pipeline_manager)
                if self.data_bridge:
                    reader.data_bridge = self.data_bridge
                if self._cache:
                    reader.set_cache(self._cache)
                if hasattr(self, '_file_exhausted_callback') and self._file_exhausted_callback:
                    reader.set_on_file_exhausted(self._file_exhausted_callback)
                self.readers[source_id] = reader
                logger.info(f"数据读取器已创建: {source_id}")
            
            logger.info(f"数据读取器已刷新，当前 {len(self.readers)} 个")
            
        except Exception as e:
            logger.error(f"刷新数据读取器失败: {e}")
    
    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """获取所有读取器的状态"""
        return {
            source_id: reader.get_status()
            for source_id, reader in self.readers.items()
        }

    def pause_reader(self, source_id: str):
        """暂停指定数据源的读取器"""
        if source_id in self.readers:
            self.readers[source_id].pause_reading()

    def resume_reader(self, source_id: str):
        """恢复指定数据源的读取器"""
        if source_id in self.readers:
            self.readers[source_id].resume_reading()

    def set_calibration_complete_callback(self, source_id: str, callback):
        """设置指定数据源的校准完成回调"""
        if source_id in self.readers:
            self.readers[source_id].set_on_calibration_complete(callback)

    def apply_new_calibration(self, source_id: str, calibration_config: Dict[str, Any]) -> bool:
        """
        对指定数据源应用新校准

        Args:
            source_id: 数据源ID
            calibration_config: 校准配置

        Returns:
            是否成功
        """
        if source_id not in self.readers:
            logger.warning(f"数据源读取器不存在: {source_id}")
            return False

        return self.readers[source_id].apply_new_calibration(calibration_config)


# 全局实例
_reader_manager_instance: Optional[DataReaderManager] = None


def get_data_reader_manager(config_manager=None, pipeline_manager=None) -> DataReaderManager:
    """获取数据读取器管理器单例"""
    global _reader_manager_instance
    
    if _reader_manager_instance is None:
        if config_manager is None or pipeline_manager is None:
            raise ValueError("首次调用需要提供 config_manager 和 pipeline_manager")
        
        _reader_manager_instance = DataReaderManager(config_manager, pipeline_manager)
    
    return _reader_manager_instance
