# -*- coding: utf-8 -*-
"""
布局模板库 v9.2 (Layout Templates)

预定义 6 种顶刊常见架构图布局模式：
1. pipeline      — 单向流水线（左→右）
2. dual_branch   — 双分支汇合（Y 形）
3. pyramid       — 金字塔分层（上→下）
4. encoder_decoder — 编码器-解码器对称结构
5. parallel      — 并行多流汇合
6. recursive     — 递归/循环结构

每种模板定义：
- 节点间距规则
- 分组渲染规则
- TikZ 样式参数
- 约束条件（最小间距、对齐方式）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Position:
    """节点位置（TikZ 坐标，单位 cm）"""
    x: float
    y: float


@dataclass
class NodeSpec:
    """节点规格"""
    id: str
    label: str
    is_innovation: bool = False
    width: float = 2.2      # cm
    height: float = 0.85    # cm
    group: str = ""


@dataclass
class EdgeSpec:
    """连接规格"""
    from_id: str
    to_id: str
    label: str = ""
    style: str = "arr"      # arr / arr_thick / arr_dashed


@dataclass
class GroupSpec:
    """分组规格"""
    id: str
    label: str
    module_ids: List[str] = field(default_factory=list)
    style: str = "group"


@dataclass
class LayoutConstraints:
    """布局约束"""
    min_gap_x: float = 1.0       # 最小水平间距 (cm)
    min_gap_y: float = 0.8       # 最小垂直间距 (cm)
    innovation_scale: float = 1.3  # 创新点模块放大倍数
    edge_margin: float = 0.5      # 边缘留白 (cm)
    align_grid: float = 0.5       # 网格对齐精度 (cm)
    balance_threshold: float = 0.3  # 左右平衡阈值


# ═══════════════════════════════════════════════════════════════
# 基类
# ═══════════════════════════════════════════════════════════════

class LayoutTemplate(ABC):
    """布局模板基类"""

    name: str = "base"
    description: str = ""

    def __init__(self):
        self.constraints = LayoutConstraints()

    @abstractmethod
    def compute_positions(
        self,
        nodes: List[NodeSpec],
        edges: List[EdgeSpec],
        groups: List[GroupSpec],
    ) -> Dict[str, Position]:
        """计算节点位置，保证无重叠 + 美观"""
        ...

    def apply_innovation_scaling(self, nodes: List[NodeSpec]) -> List[NodeSpec]:
        """创新点模块放大"""
        for node in nodes:
            if node.is_innovation:
                node.width *= self.constraints.innovation_scale
                node.height *= self.constraints.innovation_scale
        return nodes


# ═══════════════════════════════════════════════════════════════
# Pipeline 模板 — 单向流水线
# ═══════════════════════════════════════════════════════════════

class PipelineTemplate(LayoutTemplate):
    name = "pipeline"
    description = "Left-to-right sequential pipeline"

    def compute_positions(self, nodes, edges, groups):
        nodes = self.apply_innovation_scaling(nodes)
        positions = {}
        layers = _topo_layers(nodes, edges)
        col_spacing = self.constraints.min_gap_x + 2.2

        for col_idx, layer in enumerate(layers):
            n_in_col = len(layer)
            col_height = (n_in_col - 1) * (self.constraints.min_gap_y + 0.85)

            for row_idx, node_id in enumerate(layer):
                node = next((n for n in nodes if n.id == node_id), None)
                if not node:
                    continue
                x = self.constraints.edge_margin + col_idx * col_spacing
                y = col_height / 2 - row_idx * (self.constraints.min_gap_y + node.height)
                x = round(x / self.constraints.align_grid) * self.constraints.align_grid
                y = round(y / self.constraints.align_grid) * self.constraints.align_grid
                positions[node_id] = Position(x=x, y=y)
        return positions


# ═══════════════════════════════════════════════════════════════
# Dual Branch 模板 — 双分支汇合
# ═══════════════════════════════════════════════════════════════

class DualBranchTemplate(LayoutTemplate):
    name = "dual_branch"
    description = "Dual-branch merging (Y-shape)"

    def compute_positions(self, nodes, edges, groups):
        nodes = self.apply_innovation_scaling(nodes)
        positions = {}
        layers = _topo_layers(nodes, edges)
        col_spacing = self.constraints.min_gap_x + 2.2
        branch_offset_y = 2.5

        for col_idx, layer in enumerate(layers):
            n_in_col = len(layer)
            if n_in_col == 1:
                node = next((n for n in nodes if n.id == layer[0]), None)
                if node:
                    x = self.constraints.edge_margin + col_idx * col_spacing
                    positions[layer[0]] = Position(x=x, y=0)
            elif n_in_col == 2:
                for row_idx, node_id in enumerate(layer):
                    node = next((n for n in nodes if n.id == node_id), None)
                    if node:
                        x = self.constraints.edge_margin + col_idx * col_spacing
                        y = branch_offset_y / 2 - row_idx * branch_offset_y
                        positions[node_id] = Position(x=x, y=y)
            else:
                for row_idx, node_id in enumerate(layer):
                    node = next((n for n in nodes if n.id == node_id), None)
                    if node:
                        x = self.constraints.edge_margin + col_idx * col_spacing
                        total_h = (n_in_col - 1) * (self.constraints.min_gap_y + node.height)
                        y = total_h / 2 - row_idx * (self.constraints.min_gap_y + node.height)
                        positions[node_id] = Position(x=x, y=y)
        return positions


# ═══════════════════════════════════════════════════════════════
# Pyramid 模板 — 金字塔分层
# ═══════════════════════════════════════════════════════════════

class PyramidTemplate(LayoutTemplate):
    name = "pyramid"
    description = "Pyramid hierarchy (top-to-bottom)"

    def compute_positions(self, nodes, edges, groups):
        nodes = self.apply_innovation_scaling(nodes)
        positions = {}
        layers = _topo_layers(nodes, edges)
        row_spacing = self.constraints.min_gap_y + 1.0

        for row_idx, layer in enumerate(layers):
            n_in_row = len(layer)
            node_spacing = self.constraints.min_gap_x + 2.2
            total_w = (n_in_row - 1) * node_spacing

            for col_idx, node_id in enumerate(layer):
                node = next((n for n in nodes if n.id == node_id), None)
                if not node:
                    continue
                x = -total_w / 2 + col_idx * node_spacing
                y = -(row_idx * row_spacing)
                x = round(x / self.constraints.align_grid) * self.constraints.align_grid
                y = round(y / self.constraints.align_grid) * self.constraints.align_grid
                positions[node_id] = Position(x=x, y=y)
        return positions


# ═══════════════════════════════════════════════════════════════
# Encoder-Decoder 模板
# ═══════════════════════════════════════════════════════════════

class EncoderDecoderTemplate(LayoutTemplate):
    name = "encoder_decoder"
    description = "Encoder-decoder symmetric (hourglass)"

    def compute_positions(self, nodes, edges, groups):
        nodes = self.apply_innovation_scaling(nodes)
        positions = {}
        layers = _topo_layers(nodes, edges)
        col_spacing = self.constraints.min_gap_x + 2.2
        row_spacing = self.constraints.min_gap_y + 1.0

        for layer_idx, layer in enumerate(layers):
            n_in_layer = len(layer)
            for idx, node_id in enumerate(layer):
                node = next((n for n in nodes if n.id == node_id), None)
                if not node:
                    continue
                node_spacing = col_spacing
                total_w = (n_in_layer - 1) * node_spacing
                x = -total_w / 2 + idx * node_spacing
                y = -layer_idx * row_spacing
                positions[node_id] = Position(x=x, y=y)
        return positions


# ═══════════════════════════════════════════════════════════════
# Parallel 模板 — 并行多流
# ═══════════════════════════════════════════════════════════════

class ParallelTemplate(LayoutTemplate):
    name = "parallel"
    description = "Parallel streams merging"

    def compute_positions(self, nodes, edges, groups):
        nodes = self.apply_innovation_scaling(nodes)
        positions = {}
        layers = _topo_layers(nodes, edges)
        col_spacing = self.constraints.min_gap_x + 2.2
        row_spacing = self.constraints.min_gap_y + 1.0

        max_parallel = max(len(l) for l in layers) if layers else 1
        total_height = (max_parallel - 1) * row_spacing

        for col_idx, layer in enumerate(layers):
            n_in_col = len(layer)
            for row_idx, node_id in enumerate(layer):
                node = next((n for n in nodes if n.id == node_id), None)
                if not node:
                    continue
                x = self.constraints.edge_margin + col_idx * col_spacing
                if n_in_col == 1:
                    y = 0
                else:
                    y = total_height / 2 - row_idx * (total_height / (n_in_col - 1))
                positions[node_id] = Position(x=x, y=y)
        return positions


# ═══════════════════════════════════════════════════════════════
# Recursive 模板 — 循环结构
# ═══════════════════════════════════════════════════════════════

class RecursiveTemplate(LayoutTemplate):
    name = "recursive"
    description = "Recursive/cyclic structure"

    def compute_positions(self, nodes, edges, groups):
        nodes = self.apply_innovation_scaling(nodes)
        positions = {}

        if len(nodes) <= 2:
            return PipelineTemplate().compute_positions(nodes, edges, groups)

        layers = _topo_layers(nodes, edges)
        col_spacing = self.constraints.min_gap_x + 2.2
        row_spacing = self.constraints.min_gap_y + 1.5

        visited_nodes = set()
        forward_layers = []
        backward_layers = []

        for i, layer in enumerate(layers):
            layer_nodes = set(layer)
            has_back_edge = False
            for edge in edges:
                if edge.from_id in layer_nodes and edge.to_id in visited_nodes:
                    has_back_edge = True
                    break
            if has_back_edge:
                backward_layers.append((i, layer))
            else:
                forward_layers.append((i, layer))
            visited_nodes.update(layer)

        for pos, (orig_idx, layer) in enumerate(forward_layers):
            n_in_col = len(layer)
            for row_idx, node_id in enumerate(layer):
                node = next((nd for nd in nodes if nd.id == node_id), None)
                if not node:
                    continue
                x = self.constraints.edge_margin + pos * col_spacing
                y = (n_in_col - 1) / 2 * row_spacing - row_idx * row_spacing
                positions[node_id] = Position(x=x, y=y)

        n_forward = len(forward_layers)
        for pos, (orig_idx, layer) in enumerate(backward_layers):
            n_in_col = len(layer)
            for row_idx, node_id in enumerate(layer):
                node = next((nd for nd in nodes if nd.id == node_id), None)
                if not node:
                    continue
                x = self.constraints.edge_margin + (n_forward - 1 - pos) * col_spacing
                y = -2.0 - row_idx * row_spacing
                positions[node_id] = Position(x=x, y=y)

        for node in nodes:
            if node.id not in positions:
                positions[node.id] = Position(
                    x=self.constraints.edge_margin + len(positions) * col_spacing,
                    y=0,
                )
        return positions


# ═══════════════════════════════════════════════════════════════
# 模板注册与选择
# ═══════════════════════════════════════════════════════════════

TEMPLATES = {
    "pipeline": PipelineTemplate,
    "dual_branch": DualBranchTemplate,
    "pyramid": PyramidTemplate,
    "encoder_decoder": EncoderDecoderTemplate,
    "parallel": ParallelTemplate,
    "recursive": RecursiveTemplate,
}


def get_template(name: str) -> LayoutTemplate:
    """获取布局模板实例"""
    cls = TEMPLATES.get(name, PipelineTemplate)
    return cls()


def select_template(nodes, edges, suggested=""):
    """自动选择最合适的布局模板"""
    if suggested in TEMPLATES:
        return get_template(suggested)

    out_degree = {n.id: 0 for n in nodes}
    in_degree = {n.id: 0 for n in nodes}
    for e in edges:
        if e.from_id in out_degree:
            out_degree[e.from_id] += 1
        if e.to_id in in_degree:
            in_degree[e.to_id] += 1

    has_branch = any(d >= 2 for d in out_degree.values())
    has_merge = any(d >= 2 for d in in_degree.values())
    has_cycle = _detect_cycle(nodes, edges)

    if has_cycle:
        return get_template("recursive")
    if has_branch and has_merge:
        return get_template("dual_branch")
    if has_branch and not has_merge:
        return get_template("parallel")
    return get_template("pipeline")


# ═══════════════════════════════════════════════════════════════
# 拓扑工具
# ═══════════════════════════════════════════════════════════════

def _topo_layers(nodes, edges):
    """拓扑分层（Kahn 算法）"""
    node_ids = {n.id for n in nodes}
    adj = {nid: [] for nid in node_ids}
    in_deg = {nid: 0 for nid in node_ids}

    for e in edges:
        if e.from_id in adj and e.to_id in node_ids:
            adj[e.from_id].append(e.to_id)
            in_deg[e.to_id] += 1

    queue = sorted([nid for nid in node_ids if in_deg[nid] == 0])
    layers = []

    while queue:
        layer = sorted(queue)
        layers.append(layer)
        next_queue = []
        for nid in layer:
            for child in adj[nid]:
                in_deg[child] -= 1
                if in_deg[child] == 0:
                    next_queue.append(child)
        queue = next_queue

    visited = {nid for layer in layers for nid in layer}
    remaining = [n.id for n in nodes if n.id not in visited]
    if remaining:
        if layers:
            layers[-1].extend(remaining)
        else:
            layers.append(remaining)

    return layers


def _detect_cycle(nodes, edges):
    """检测图中是否有环"""
    node_ids = {n.id for n in nodes}
    adj = {nid: [] for nid in node_ids}
    for e in edges:
        if e.from_id in adj:
            adj[e.from_id].append(e.to_id)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in node_ids}

    def dfs(node):
        color[node] = GRAY
        for child in adj.get(node, []):
            if child not in color:
                continue
            if color[child] == GRAY:
                return True
            if color[child] == WHITE and dfs(child):
                return True
        color[node] = BLACK
        return False

    for nid in node_ids:
        if color[nid] == WHITE:
            if dfs(nid):
                return True
    return False
