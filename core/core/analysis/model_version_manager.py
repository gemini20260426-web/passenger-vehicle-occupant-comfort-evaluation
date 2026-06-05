"""
模型版本管理器 — 快照保存 + 回滚 + 校验

基于专家评测报告 COMPREHENSIVE_EVALUATION_REPORT.md 第三部分 8.5 节。
"""

import os
import pickle
import hashlib
import shutil
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ModelSnapshot:
    """模型快照"""
    version: str
    model_params: dict
    feature_config: dict
    thresholds: dict
    timestamp: float = field(default_factory=time.time)
    checksum: str = ""
    metadata: dict = field(default_factory=dict)


class ModelVersionManager:
    """模型版本管理

    功能:
    1. 保存/加载模型快照 (流式+离线共用同一文件)
    2. 版本回滚
    3. 校验和验证
    4. 自动清理旧版本
    """

    def __init__(self, model_dir: str = 'models/', max_versions: int = 10):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.max_versions = max_versions
        self.current_version: str = 'v1.0.0'
        self.version_history: List[ModelSnapshot] = []
        self._load_version_history()

    def save(self, model: Any, feature_config: dict, thresholds: dict,
             version: str, metadata: dict = None) -> str:
        """保存模型快照 (流式+离线共用同一文件)

        Args:
            model: 模型对象 (需支持 get_params() 或 pickle 序列化)
            feature_config: 特征配置
            thresholds: 阈值表
            version: 版本号
            metadata: 额外元数据

        Returns:
            保存路径
        """
        snapshot = ModelSnapshot(
            version=version,
            model_params=self._extract_model_params(model),
            feature_config=feature_config,
            thresholds=thresholds,
            timestamp=time.time(),
            metadata=metadata or {},
        )

        # 计算校验和
        snapshot_data = pickle.dumps(snapshot.model_params)
        snapshot.checksum = hashlib.sha256(snapshot_data).hexdigest()[:8]

        # 保存文件
        path = self.model_dir / f'event_detector_{version}.pkl'
        with open(path, 'wb') as f:
            pickle.dump(snapshot, f)

        # 同时保存为 latest
        latest_path = self.model_dir / 'event_detector_latest.pkl'
        shutil.copy(path, latest_path)

        self.version_history.append(snapshot)
        self.current_version = version
        self._cleanup_old_versions()

        logger.info(
            f"模型已保存: {version} "
            f"(checksum={snapshot.checksum}, "
            f"features={len(feature_config)}, "
            f"thresholds={len(thresholds)})"
        )
        return str(path)

    def load(self, version: str = 'latest') -> Optional[dict]:
        """加载模型 (流式/离线统一入口)

        Returns:
            {'model_params': ..., 'feature_config': ..., 'thresholds': ...}
        """
        path = self.model_dir / f'event_detector_{version}.pkl'
        if not path.exists():
            logger.error(f"模型文件不存在: {path}")
            return None

        with open(path, 'rb') as f:
            snapshot: ModelSnapshot = pickle.load(f)

        # 校验和验证
        expected = snapshot.checksum
        actual = hashlib.sha256(
            pickle.dumps(snapshot.model_params)
        ).hexdigest()[:8]
        if expected != actual:
            logger.warning(f"校验和不匹配: {expected} vs {actual}")

        self.current_version = snapshot.version
        logger.info(
            f"模型已加载: {snapshot.version} "
            f"(checksum={snapshot.checksum})"
        )

        return {
            'model_params': snapshot.model_params,
            'feature_config': snapshot.feature_config,
            'thresholds': snapshot.thresholds,
            'version': snapshot.version,
            'metadata': snapshot.metadata,
        }

    def rollback(self, version: str) -> bool:
        """回滚到指定版本"""
        path = self.model_dir / f'event_detector_{version}.pkl'
        if not path.exists():
            logger.error(f"回滚目标版本不存在: {version}")
            return False

        # 复制目标版本到 latest
        latest_path = self.model_dir / 'event_detector_latest.pkl'
        shutil.copy(path, latest_path)
        self.current_version = version

        logger.info(f"已回滚到版本: {version}")
        return True

    def list_versions(self) -> List[dict]:
        """列出所有版本"""
        versions = []
        for f in self.model_dir.glob('event_detector_v*.pkl'):
            if f.name == 'event_detector_latest.pkl':
                continue
            with open(f, 'rb') as fh:
                snapshot: ModelSnapshot = pickle.load(fh)
            versions.append({
                'version': snapshot.version,
                'checksum': snapshot.checksum,
                'timestamp': snapshot.timestamp,
                'features': len(snapshot.feature_config),
                'thresholds': len(snapshot.thresholds),
                'size_bytes': f.stat().st_size,
            })

        versions.sort(key=lambda x: x['timestamp'], reverse=True)
        return versions

    def get_current_version(self) -> str:
        """获取当前版本"""
        return self.current_version

    def compare_versions(self, v1: str, v2: str) -> dict:
        """比较两个版本"""
        s1 = self.load(v1)
        s2 = self.load(v2)

        if not s1 or not s2:
            return {'error': 'version not found'}

        t1 = s1['thresholds']
        t2 = s2['thresholds']

        diff = {}
        all_keys = set(t1.keys()) | set(t2.keys())
        for key in all_keys:
            v1_val = t1.get(key)
            v2_val = t2.get(key)
            if v1_val != v2_val:
                diff[key] = {'v1': v1_val, 'v2': v2_val}

        return {
            'v1': v1, 'v2': v2,
            'threshold_diff_count': len(diff),
            'threshold_diffs': diff,
            'v1_features': len(s1['feature_config']),
            'v2_features': len(s2['feature_config']),
        }

    def export_manifest(self) -> dict:
        """导出模型清单"""
        return {
            'current_version': self.current_version,
            'model_dir': str(self.model_dir),
            'versions': self.list_versions(),
            'total_versions': len(self.version_history),
        }

    def _extract_model_params(self, model: Any) -> dict:
        """提取模型参数"""
        if hasattr(model, 'get_params'):
            return model.get_params()
        elif hasattr(model, 'models'):
            return {k: v.get_params() if hasattr(v, 'get_params') else str(type(v))
                    for k, v in model.models.items()}
        return {'type': str(type(model))}

    def _load_version_history(self) -> None:
        """加载版本历史"""
        for f in sorted(self.model_dir.glob('event_detector_v*.pkl')):
            if f.name == 'event_detector_latest.pkl':
                continue
            try:
                with open(f, 'rb') as fh:
                    snapshot = pickle.load(fh)
                self.version_history.append(snapshot)
            except Exception as e:
                logger.warning(f"加载版本文件失败 {f}: {e}")

        if self.version_history:
            self.version_history.sort(key=lambda x: x.timestamp, reverse=True)
            self.current_version = self.version_history[0].version

    def _cleanup_old_versions(self) -> None:
        """清理旧版本 (保留最近 max_versions 个)"""
        if len(self.version_history) <= self.max_versions:
            return

        self.version_history.sort(key=lambda x: x.timestamp, reverse=True)
        to_remove = self.version_history[self.max_versions:]

        for snapshot in to_remove:
            path = self.model_dir / f'event_detector_{snapshot.version}.pkl'
            if path.exists():
                path.unlink()
                logger.debug(f"已清理旧版本: {snapshot.version}")

        self.version_history = self.version_history[:self.max_versions]