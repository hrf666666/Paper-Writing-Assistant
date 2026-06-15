# -*- coding: utf-8 -*-
"""
PipelineContext — 全局共享状态容器（单一真相源）

所有 Phase Handler 读写同一个 PipelineContext 实例。
替代 loop.py 中散落的 22 个 self._xxx 实例属性。

设计原则：
1. 唯一数据源 — 所有状态集中在一个对象中
2. 可序列化 — to_checkpoint_dict() / from_checkpoint_dict() 支持断点恢复
3. 类型安全 — dataclass 提供明确的类型标注
4. 可扩展 — 新增字段不影响已有代码
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Dict, List, Any


@dataclass
class PipelineContext:
    """Pipeline 全局共享状态。"""

    # --- 核心项目数据 (Phase 0) ---
    project_data: Dict[str, Any] = field(default_factory=dict)
    ref_data: Dict[str, Any] = field(default_factory=dict)

    # --- 生成的内容 ---
    chapters: Dict[Any, str] = field(default_factory=dict)
    abstract: str = ""

    # --- 预生成分析结果 (Phase 0.5-0.65) ---
    reference_pool: List[Any] = field(default_factory=list)
    outline: Dict[str, Any] = field(default_factory=dict)
    motivation_thread: str = ""
    exemplar_dossier: Dict[str, Any] = field(default_factory=dict)
    style_profile: Dict[str, Any] = field(default_factory=dict)
    citation_bank: Dict[str, Any] = field(default_factory=dict)
    rationale_matrix: Dict[str, Any] = field(default_factory=dict)
    ablation_results: Dict[str, Any] = field(default_factory=dict)

    # --- 学习到的风格 (Phase 0.6-0.65) ---
    journal_style: Dict[str, Any] = field(default_factory=dict)
    content_strategy: Dict[str, Any] = field(default_factory=dict)

    # --- 验证上下文 ---
    paper_context: Dict[str, Any] = field(default_factory=dict)

    # --- 引用映射 ---
    cite_key_map: Dict[str, Any] = field(default_factory=dict)
    title_to_key: Dict[str, str] = field(default_factory=dict)

    # ---- 序列化 ----

    def to_checkpoint_dict(self) -> Dict[str, Any]:
        """序列化为可存储的字典（用于 CheckpointManager）。"""
        import dataclasses
        return dataclasses.asdict(self)

    @classmethod
    def from_checkpoint_dict(cls, data: Dict[str, Any]) -> PipelineContext:
        """从存储的字典反序列化。忽略未知字段，缺失字段使用默认值。"""
        valid_names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid_names})

    def save_to_checkpoint(self, checkpoint_mgr) -> None:
        """将所有字段保存到 CheckpointManager。"""
        for f in fields(self):
            checkpoint_mgr.save_state(f.name, getattr(self, f.name))

    def load_from_checkpoint(self, checkpoint_mgr) -> bool:
        """从 CheckpointManager 加载所有字段。返回是否有数据。"""
        has_data = False
        for f in fields(self):
            val = checkpoint_mgr.get_state(f.name, f.default_factory() if f.default_factory else f.default)
            setattr(self, f.name, val)
            if val:
                has_data = True
        return has_data
