#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型持久化 — LightGBM 模型的保存/加载/版本管理

支持:
  - 模型序列化 (pickle + JSON 元数据)
  - 版本校验 (事件类型列表一致性检查)
  - 默认模型路径管理
  - 回退机制 (模型文件缺失时返回 None，不中断流程)
"""

import os
import json
import pickle
import logging
from datetime import datetime
from typing import Optional, Any, Dict, List

logger = logging.getLogger(__name__)

# 默认模型存储目录
DEFAULT_MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'models',
)

DEFAULT_MODEL_FILENAME = 'lgbm_25class_classifier.pkl'
DEFAULT_META_FILENAME = 'lgbm_25class_classifier_meta.json'


class ModelPersistence:
    """LightGBM 模型持久化管理器

    用法:
        persistence = ModelPersistence()
        persistence.save(model, event_types, feature_names, metrics)
        model, meta = persistence.load()
    """

    def __init__(self, model_dir: Optional[str] = None):
        self._model_dir = model_dir or DEFAULT_MODEL_DIR
        os.makedirs(self._model_dir, exist_ok=True)

    @property
    def model_path(self) -> str:
        return os.path.join(self._model_dir, DEFAULT_MODEL_FILENAME)

    @property
    def meta_path(self) -> str:
        return os.path.join(self._model_dir, DEFAULT_META_FILENAME)

    def save(
        self,
        model: Any,
        event_types: List[str],
        feature_names: List[str],
        metrics: Optional[Dict[str, float]] = None,
        calibration: Optional[Dict] = None,
    ) -> str:
        """保存模型及元数据

        Args:
            model: 已训练的 LightGBM 模型
            event_types: 25 类事件类型列表
            feature_names: 55 维特征名列表
            metrics: 训练评估指标 (accuracy, f1_macro, etc.)
            calibration: Phase 2 概率校准参数

        Returns:
            模型文件路径
        """
        # 保存模型
        with open(self.model_path, 'wb') as f:
            pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)

        # 保存元数据
        meta = {
            'version': '1.0.0',
            'created_at': datetime.now().isoformat(),
            'model_type': 'LightGBM',
            'framework_version': self._get_lgbm_version(),
            'n_classes': len(event_types),
            'event_types': event_types,
            'n_features': len(feature_names),
            'feature_names': feature_names,
            'metrics': metrics or {},
            'calibration': calibration or {},
        }
        with open(self.meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        logger.info(
            f"模型已保存: {self.model_path} "
            f"(n_classes={len(event_types)}, n_features={len(feature_names)})"
        )
        return self.model_path

    def load(self) -> tuple:
        """加载模型及元数据

        Returns:
            (model, meta_dict) — 如果模型文件不存在则返回 (None, {})
        """
        if not os.path.exists(self.model_path):
            logger.warning(f"模型文件不存在: {self.model_path}")
            return None, {}

        try:
            with open(self.model_path, 'rb') as f:
                model = pickle.load(f)
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return None, {}

        meta = {}
        if os.path.exists(self.meta_path):
            try:
                with open(self.meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
            except Exception as e:
                logger.warning(f"加载元数据失败: {e}")

        logger.info(
            f"模型已加载: {self.model_path} "
            f"(n_classes={meta.get('n_classes', '?')}, "
            f"created={meta.get('created_at', '?')})"
        )
        return model, meta

    def validate_event_types(self, expected_types: List[str]) -> bool:
        """校验模型事件类型与系统定义是否一致

        Args:
            expected_types: 系统当前定义的 25 类事件类型

        Returns:
            True 如果一致，False 如果不一致
        """
        model, meta = self.load()
        if model is None:
            return False

        model_types = set(meta.get('event_types', []))
        expected_set = set(expected_types)

        if model_types != expected_set:
            missing = expected_set - model_types
            extra = model_types - expected_set
            logger.warning(
                f"事件类型不匹配: "
                f"模型有{len(model_types)}类, 系统有{len(expected_set)}类; "
                f"缺失={missing}, 多余={extra}"
            )
            return False
        return True

    def model_exists(self) -> bool:
        return os.path.exists(self.model_path)

    @staticmethod
    def _get_lgbm_version() -> str:
        try:
            import lightgbm
            return lightgbm.__version__
        except Exception:
            return 'unknown'

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息摘要 (不加载模型本体)"""
        if not os.path.exists(self.meta_path):
            return {'exists': False}
        try:
            with open(self.meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            meta['exists'] = True
            meta['model_path'] = self.model_path
            return meta
        except Exception:
            return {'exists': False}