#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指标依赖图 DAG (A4) — 构建指标计算依赖关系，共享中间结果避免重复计算

架构:
  PSD ──→ Wk ──→ SEAT_Z, AW_Z, VDV_Z  (共享PSD和加权结果)
  SRS ──→ MRS, Q, PV, ATT             (共享SRS一次性计算)
  Rainflow ──→ FDS_D, FDS_R, RFC_CC     (共享Rainflow结果)
  STFT ──→ FC, KT, CE                    (共享STFT结果)
  Integration ──→ DISP_TR, DISP_HR       (共享积分中间结果)

使用:
  1. 构建 DAG: dag = MetricDAG()
  2. 执行计算: results = dag.execute(data_window, metrics)
  3. 获取子图: subgraph = dag.get_subgraph(metric_ids)
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MetricNode:
    """DAG节点: 一个可计算的指标"""
    metric_id: str
    depends_on: FrozenSet[str] = field(default_factory=frozenset)  # 依赖的其他指标
    produces: FrozenSet[str] = field(default_factory=frozenset)     # 产生的中间结果键
    compute_fn: Optional[Callable] = None                            # 计算函数
    category: str = 'metric'                                         # 节点类别: metric / operator / data


# ═══════════════════════════════════════════════════════════════
#  核心DAG定义: 按算子分组，明确共享中间结果
# ═══════════════════════════════════════════════════════════════

METRIC_DEPENDENCY_GRAPH: Dict[str, List[str]] = {
    # ── PSD算子共享 ──
    'PSD_Z': [],  # 中间结果: az→PSD
    'SEAT_Z': ['PSD_Z', 'PSD_FLOOR_Z'],
    'AW_Z': ['PSD_Z'],
    'VDV_Z': ['PSD_Z'],
    'PSD_FLOOR_Z': [],

    # ── Wk加权共享 ──
    'WK_WEIGHTED_Z': [],  # 中间结果: az→Wk时域加权
    'AW_Z_weighted': ['WK_WEIGHTED_Z'],
    'VDV_Z_weighted': ['WK_WEIGHTED_Z'],

    # ── SRS算子共享 ──
    'SRS_RESULT': [],
    'SRS_MRS': ['SRS_RESULT'],
    'SRS_Q': ['SRS_RESULT'],
    'SRS_PV': ['SRS_RESULT'],
    'SRS_ATT': ['SRS_RESULT'],

    # ── Rainflow算子共享 ──
    'RAINFLOW_RESULT': [],
    'RFC_CC': ['RAINFLOW_RESULT'],
    'FDS_D': ['RAINFLOW_RESULT'],
    'FDS_R': ['RAINFLOW_RESULT'],

    # ── STFT算子共享 ──
    'STFT_RESULT': [],
    'STFT_FC': ['STFT_RESULT'],
    'STFT_KT': ['STFT_RESULT'],
    'STFT_CE': ['STFT_RESULT'],

    # ── CSD算子共享 ──
    'CSD_RESULT': [],
    'TR_Z': ['CSD_RESULT'],

    # ── Vector合成共享 ──
    'VECTOR_XYZ': [],
    'ACC_RMS': ['VECTOR_XYZ'],
    'ACC_PEAK': ['VECTOR_XYZ'],
    'ACC_H_PEAK': ['VECTOR_XYZ'],
    'OVTV': ['VECTOR_XYZ'],
    'R_FACTOR': ['VECTOR_XYZ'],

    # ── Vector XY合成 ──
    'VECTOR_XY': [],
    'SEAT_XY': ['VECTOR_XY'],
    'AW_XY': ['VECTOR_XY'],

    # ── Integration共享 ──
    'INTEGRATION_RESULT_Z': [],
    'DISP_TR': ['INTEGRATION_RESULT_Z'],
    'INTEGRATION_RESULT_3D': [],
    'DISP_HR': ['INTEGRATION_RESULT_3D'],

    # ── CFC滤波共享 ──
    'CFC600_RESULT': [],
    'JERK_H': ['CFC600_RESULT'],
    'HIC15': ['CFC600_RESULT'],

    # ── ISO2631-5 ──
    'S_D': [],

    # ── 频段衰减 ──
    'BAND_ATT_01_05': [],
    'BAND_ATT_05_1': [],
    'BAND_ATT_1_5': [],
    'BAND_ATT_5_20': [],
    'BAND_ATT_20_80': [],

    # ── 全时域统计 (每项独立，无共享) ──
    # 所有 RMS/Peak/Crest/VDV/Skew/Kurt/MAV/Impf 指标直接计算
}


class MetricDAG:
    """指标依赖图 — 拓扑排序 + 中间结果缓存

    解决 A4: "SEAT_Z / VDV_Z 各自独立计算 PSD, 重复劳动"
    构建 DAG: PSD→Wk→SEAT_Z, AW_Z, VDV_Z 共享中间结果
    """

    def __init__(self):
        self._nodes: Dict[str, MetricNode] = {}
        self._adjacency: Dict[str, List[str]] = defaultdict(list)
        self._reverse_adjacency: Dict[str, List[str]] = defaultdict(list)
        self._topo_order: Optional[List[str]] = None
        self._dirty = True

    def add_node(self, node: MetricNode):
        """添加节点"""
        self._nodes[node.metric_id] = node
        for dep in node.depends_on:
            self._adjacency[dep].append(node.metric_id)
            self._reverse_adjacency[node.metric_id].append(dep)
        self._dirty = True

    def add_dependency(self, source: str, target: str):
        """添加依赖: target 依赖 source"""
        self._adjacency[source].append(target)
        self._reverse_adjacency[target].append(source)
        self._dirty = True

    def get_dependencies(self, metric_id: str) -> List[str]:
        """获取某指标的所有直接依赖"""
        return list(self._reverse_adjacency.get(metric_id, []))

    def get_dependents(self, metric_id: str) -> List[str]:
        """获取依赖某指标的所有后续指标 (谁依赖我)"""
        return list(self._adjacency.get(metric_id, []))

    def get_transitive_dependencies(self, metric_id: str) -> Set[str]:
        """获取某指标的所有传递依赖 (BFS)"""
        visited = set()
        queue = list(self._reverse_adjacency.get(metric_id, []))
        while queue:
            dep = queue.pop(0)
            if dep not in visited:
                visited.add(dep)
                queue.extend(self._reverse_adjacency.get(dep, []))
        return visited

    def topological_sort(self) -> List[str]:
        """拓扑排序: 保证先计算依赖项"""
        if not self._dirty and self._topo_order is not None:
            return self._topo_order

        in_degree = {nid: len(self._reverse_adjacency.get(nid, []))
                     for nid in self._nodes}
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in self._adjacency.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self._nodes):
            # 存在循环依赖
            remaining = set(self._nodes.keys()) - set(result)
            logger.warning(f"DAG存在循环依赖: {remaining}")
            # 打破循环: 将剩余节点追加
            result.extend(remaining)

        self._topo_order = result
        self._dirty = False
        return result

    def get_computation_order(self, metric_ids: List[str]) -> List[str]:
        """获取指定指标集的计算顺序 (包含所需依赖)

        排除已在 metric_ids 中的依赖项（它们本身就是目标），
        只返回需要计算的中间结果 + 目标指标。
        """
        target_set = set(metric_ids)
        needed = set(metric_ids)

        # 收集所有传递依赖
        for mid in metric_ids:
            needed.update(self.get_transitive_dependencies(mid))

        # 按拓扑序排列
        topo = self.topological_sort()
        ordered = [n for n in topo if n in needed]
        return ordered

    def get_subgraph(self, metric_ids: List[str]) -> 'MetricDAG':
        """提取子图: 仅包含 metric_ids 及其依赖"""
        sub = MetricDAG()
        target_set = set(metric_ids)
        needed = set(metric_ids)
        for mid in metric_ids:
            needed.update(self.get_transitive_dependencies(mid))

        for nid in needed:
            if nid in self._nodes:
                sub.add_node(self._nodes[nid])
        return sub

    def build_from_dict(self, graph_dict: Dict[str, List[str]]):
        """从字典构建DAG"""
        for node_id, deps in graph_dict.items():
            node = MetricNode(
                metric_id=node_id,
                depends_on=frozenset(deps),
                produces=frozenset([node_id]),
            )
            self.add_node(node)

    @staticmethod
    def from_default_graph() -> 'MetricDAG':
        """从默认 METRIC_DEPENDENCY_GRAPH 构建"""
        dag = MetricDAG()
        dag.build_from_dict(METRIC_DEPENDENCY_GRAPH)
        return dag


# ═══════════════════════════════════════════════════════════
#  依赖图可视化 (用于调试和文档)
# ═══════════════════════════════════════════════════════════

def visualize_dag(dag: MetricDAG, output_format: str = 'mermaid') -> str:
    """生成DAG可视化 (Mermaid格式)

    Args:
        dag: MetricDAG实例
        output_format: 'mermaid' | 'dot'

    Returns:
        可视化字符串
    """
    if output_format == 'mermaid':
        lines = ['graph TD']
        for node_id, node in dag._nodes.items():
            for dep in node.depends_on:
                lines.append(f'    {dep}[{dep}] --> {node_id}[{node_id}]')
        return '\n'.join(lines)
    elif output_format == 'dot':
        lines = ['digraph MetricDAG {', '  rankdir=TB;']
        for node_id, node in dag._nodes.items():
            for dep in node.depends_on:
                lines.append(f'  "{dep}" -> "{node_id}";')
        lines.append('}')
        return '\n'.join(lines)
    return ''


# ═══════════════════════════════════════════════════════════
#  DAG执行器: 按拓扑序执行，缓存中间结果
# ═══════════════════════════════════════════════════════════

class DAGExecutor:
    """DAG执行器 — 按依赖关系执行计算管线

    特性:
      - 按拓扑序执行，确保依赖先计算
      - 自动缓存中间结果 (如 PSD、SRS、Rainflow 等)
      - 支持并行执行同层级节点 (A5预备)
      - 返回计算后的完整结果字典
    """

    def __init__(self, dag: MetricDAG):
        self.dag = dag
        self._cache: Dict[str, Any] = {}

    def execute(self,
                compute_fn_map: Dict[str, Callable],
                data_window: Dict[str, Any],
                metric_ids: List[str],
                clear_cache: bool = True) -> Dict[str, float]:
        """按DAG顺序执行指标计算

        Args:
            compute_fn_map: {metric_id: callable} 每个指标的计算函数
                            函数签名: fn(data_window, cache) -> float
            data_window: 数据窗口
            metric_ids: 需要计算的指标列表
            clear_cache: 是否在执行前清空缓存

        Returns:
            {metric_id: value} 计算结果
        """
        if clear_cache:
            self._cache.clear()

        # 获取计算顺序: 包含所有依赖 + 目标指标
        exec_order = self.dag.get_computation_order(metric_ids)

        results = {}
        for node_id in exec_order:
            if node_id not in compute_fn_map:
                # 中间结果节点，无直接计算函数，跳过
                continue

            try:
                value = compute_fn_map[node_id](data_window, self._cache)
                results[node_id] = value
                # 中间结果也缓存
                self._cache[node_id] = value
            except Exception as e:
                logger.error(f"DAG执行失败 [{node_id}]: {e}")
                results[node_id] = float('nan')
                self._cache[node_id] = None

        return results

    def cache_intermediate(self, key: str, value: Any):
        """手动缓存中间结果"""
        self._cache[key] = value

    def get_cached(self, key: str) -> Optional[Any]:
        """获取缓存的中间结果"""
        return self._cache.get(key)

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()


# ═══════════════════════════════════════════════════════════
#  A5: 并行计算框架
# ═══════════════════════════════════════════════════════════

class ParallelMetricExecutor:
    """并行指标计算执行器 (A5)

    使用 concurrent.futures.ThreadPoolExecutor 对可并行化的指标计算
    进行多线程加速。按DAG层级分组，同层级节点可并行计算。

    指标计算时间从 O(n) → O(log n) (以DAG深度为界)
    """

    def __init__(self, dag: MetricDAG, max_workers: int = None):
        self.dag = dag
        self.max_workers = max_workers or min(8, (__import__('os').cpu_count() or 4))

    def _get_level_groups(self, metric_ids: List[str]) -> List[List[str]]:
        """按DAG层级分组

        层级定义: 无依赖的节点为 level 0，依赖 level N 的节点为 level N+1
        同层级节点可并行计算（互不依赖）
        """
        needed = set(metric_ids)
        for mid in metric_ids:
            needed.update(self.dag.get_transitive_dependencies(mid))

        # BFS 分层
        levels = []
        in_degree = {nid: len(self.dag.get_dependencies(nid)) for nid in needed}
        current_level = [nid for nid in needed if in_degree.get(nid, 0) == 0]

        while current_level:
            levels.append(current_level)
            next_level = []
            for node in current_level:
                for dependent in self.dag.get_dependents(node):
                    if dependent in needed:
                        in_degree[dependent] = max(0, in_degree.get(dependent, 1) - 1)
                        if in_degree[dependent] == 0:
                            next_level.append(dependent)
            current_level = next_level

        return levels

    def execute(self,
                compute_fn_map: Dict[str, Callable],
                data_window: Dict[str, Any],
                metric_ids: List[str]) -> Dict[str, float]:
        """并行执行指标计算

        同层级节点并发执行，层级间串行（保证依赖关系）
        """
        import concurrent.futures

        cache = {}
        results = {}
        levels = self._get_level_groups(metric_ids)

        for level_idx, level_nodes in enumerate(levels):
            # 过滤出有计算函数的节点
            computable = [n for n in level_nodes if n in compute_fn_map]

            if not computable:
                continue

            if len(computable) == 1:
                # 单节点直接计算
                node = computable[0]
                try:
                    value = compute_fn_map[node](data_window, cache)
                    results[node] = value
                    cache[node] = value
                except Exception as e:
                    logger.error(f"并行计算失败 [{node}]: {e}")
                    results[node] = float('nan')
            else:
                # 多节点并行
                with concurrent.futures.ThreadPoolExecutor(
                        max_workers=min(self.max_workers, len(computable))
                ) as executor:
                    futures = {}
                    for node in computable:
                        future = executor.submit(
                            self._safe_compute, compute_fn_map[node],
                            data_window, cache, node
                        )
                        futures[future] = node

                    for future in concurrent.futures.as_completed(futures):
                        node = futures[future]
                        try:
                            value = future.result(timeout=30)
                            results[node] = value
                            cache[node] = value
                        except Exception as e:
                            logger.error(f"并行计算超时/失败 [{node}]: {e}")
                            results[node] = float('nan')

        return results

    @staticmethod
    def _safe_compute(fn: Callable, data_window: Dict, cache: Dict, node_id: str) -> float:
        """安全计算包装"""
        try:
            return fn(data_window, cache)
        except Exception as e:
            logger.error(f"安全计算失败 [{node_id}]: {e}")
            return float('nan')