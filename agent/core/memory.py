# -*- coding: utf-8 -*-
"""
LayeredMemory —— 分层记忆 + 上下文治理 (v13 PR3)

解决 architecture.md 宣称但从未实现的"恒定上下文/3层记忆/5000字预算"。
核心痛点（codereview 实测）：
  - citation_context 每章重注 7 次（10-30KB×7），全 run 最大上下文浪费
  - innovation_summary / experiment_design / model_architecture 反复重发
  - 无 token 计数器
  - 旧 MemoryManager 只喂 THINK，从不喂生成

设计：
  LAYER_WORKING  — 当前任务工作变量（小，<500字）
  LAYER_EPISODIC — 短期：最近 N 步的决策/分数/Findings（滚动，<3000字）
  LAYER_SEMANTIC — 长期：压缩后的项目知识（引用上下文/创新点摘要/事实清单/死路），
                   重文本进此层一次，按 intent 检索切片而非全量重注

assemble(intent, budget) 按生成意图检索式组装 ≤budget 的上下文。
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# 上下文包：把"每次都要重新拼"的重文本缓存起来
# ──────────────────────────────────────────────────────────────

@dataclass
class _CachedBlob:
    """一个缓存的重文本块 + 其依赖指纹（用于失效判断）。"""
    key: str                       # "citation_context" | "innovation_summary" | ...
    content: str
    fingerprint: str               # 依赖数据的 hash，变了就失效
    char_count: int = 0
    computed_at: float = field(default_factory=time.time)

    def __post_init__(self):
        self.char_count = len(self.content)


def _fingerprint(obj: Any) -> str:
    """对依赖对象算稳定指纹（基于内容，非 id）。"""
    try:
        h = hashlib.md5(repr(obj).encode("utf-8", errors="ignore")).hexdigest()[:12]
        return h
    except Exception:
        return "unknown"


# ──────────────────────────────────────────────────────────────
# LayeredMemory
# ──────────────────────────────────────────────────────────────

class LayeredMemory:
    """三层记忆 + 上下文包缓存。

    用法：
        mem = LayeredMemory()
        # 缓存重文本（带依赖指纹，依赖变了自动失效重算）
        ctx = mem.get_or_compute(
            "citation_context",
            depends=[citation_bank, cite_key_map],
            compute=lambda: _build_citation_context_uncached(...),
        )
        # 按意图组装 prompt 上下文
        block = mem.assemble("generate_ch3", budget_chars=6000)
    """

    # 各层预算（字符）
    WORKING_BUDGET = 500
    EPISODIC_BUDGET = 3000
    EPISODIC_MAX_ENTRIES = 40

    def __init__(self):
        # WORKING: 当前任务的临时变量 {name: value}
        self._working: Dict[str, Any] = {}
        # EPISODIC: 滚动日志 [(timestamp, category, text)]
        self._episodic: Deque[tuple] = deque(maxlen=self.EPISODIC_MAX_ENTRIES)
        # SEMANTIC: 长期知识 + 缓存的重文本 {key: _CachedBlob}
        self._semantic: Dict[str, _CachedBlob] = {}
        # 死路（避免重复尝试的策略）
        self._dead_ends: List[str] = []
        # 上下文使用统计（供观测）
        self._stats = {"cache_hits": 0, "cache_misses": 0, "assembled_chars": 0}

    # ── WORKING 层 ──

    def set_working(self, name: str, value: Any):
        self._working[name] = value

    def get_working(self, name: str, default=None):
        return self._working.get(name, default)

    def clear_working(self):
        self._working.clear()

    # ── EPISODIC 层 ──

    def log(self, category: str, text: str):
        """记一条短期记忆（决策/分数/Finding 摘要）。自动滚动。"""
        self._episodic.append((time.time(), category, text[:400]))

    def recent(self, n: int = 8, category: Optional[str] = None) -> List[str]:
        out = []
        for ts, cat, text in reversed(self._episodic):
            if category and cat != category:
                continue
            out.append(f"[{cat}] {text}")
            if len(out) >= n:
                break
        return out

    # ── SEMANTIC 层：重文本缓存 ──

    def get_or_compute(self, key: str, depends: List[Any],
                        compute: Callable[[], str]) -> str:
        """核心：重文本只算一次，依赖指纹变了才重算。

        这是消除 citation_context 重注 7 次的关键：
        第一次调用 compute() 并缓存；后续 6 次命中缓存（除非 citation_bank 变了）。
        """
        fp = _fingerprint(depends)
        cached = self._semantic.get(key)
        if cached is not None and cached.fingerprint == fp:
            self._stats["cache_hits"] += 1
            return cached.content
        # miss → 重算
        content = compute() or ""
        self._semantic[key] = _CachedBlob(key=key, content=content, fingerprint=fp)
        self._stats["cache_misses"] += 1
        logger.debug(f"[memory] 缓存块 '{key}' {'命中' if cached else '新建'} "
                     f"({len(content)} chars, fp={fp})")
        return content

    def invalidate(self, key: str):
        """显式失效某缓存块（依赖变更但未自动检测时用）。"""
        self._semantic.pop(key, None)

    def semantic_get(self, key: str) -> Optional[str]:
        b = self._semantic.get(key)
        return b.content if b else None

    def semantic_set(self, key: str, content: str, depends: List[Any] = None):
        """直接写入一个语义层条目。"""
        fp = _fingerprint(depends) if depends else "manual"
        self._semantic[key] = _CachedBlob(key=key, content=content, fingerprint=fp)

    # ── 死路 ──

    def add_dead_end(self, desc: str):
        if desc not in self._dead_ends:
            self._dead_ends.append(desc)

    def is_dead_end(self, desc: str) -> bool:
        return any(desc in d for d in self._dead_ends)

    # ── 检索式组装 ──

    # 意图 → 相关语义层 key 的映射（哪些重文本与该生成任务相关）
    _INTENT_KEYS: Dict[str, List[str]] = {
        "generate_ch1": ["citation_context", "innovation_summary", "fact_sheet"],
        "generate_ch2": ["citation_context", "reference_pool_summary"],
        "generate_ch3": ["citation_context", "innovation_summary", "model_arch_slice", "fact_sheet"],
        "generate_ch4": ["citation_context", "experiment_design_slice", "fact_sheet"],
        "generate_ch5": ["citation_context", "innovation_summary", "fact_sheet"],
        "generate_abstract": ["fact_sheet", "innovation_summary"],
        "revise": ["fact_sheet"],   # 修订只需事实约束，不需全量引用
        "plan_next": [],            # 规划用 episodic
    }

    def assemble(self, intent: str, budget_chars: int = 6000,
                 extra: Optional[Dict[str, str]] = None) -> str:
        """按生成意图检索式组装 ≤budget 的上下文。

        - 相关语义层切片（citation_context 等，按 intent 选）
        - 最近 episodic（决策/分数，少量）
        - extra: 调用方临时追加的上下文（如 previous_chapters）
        """
        parts: List[str] = []
        used = 0
        keys = self._INTENT_KEYS.get(intent, [])

        # 1. 语义层相关切片
        for k in keys:
            blob = self._semantic.get(k)
            if not blob or not blob.content:
                continue
            if used + len(blob.content) > budget_chars:
                # 超预算：截取（简单尾部截断，保留头部事实）
                remain = budget_chars - used
                if remain > 200:
                    parts.append(blob.content[:remain] + "\n...[truncated]")
                    used = budget_chars
                break
            parts.append(blob.content)
            used += len(blob.content)

        # 2. episodic（仅在 plan/revise 意图下注入少量）
        if intent in ("plan_next", "revise"):
            recent = self.recent(5)
            if recent and used + 500 < budget_chars:
                ep = "\n".join(recent)[: min(800, budget_chars - used)]
                parts.append(f"<recent_decisions>\n{ep}\n</recent_decisions>")
                used += len(ep)

        # 3. extra
        if extra:
            for k, v in extra.items():
                if used + len(v) > budget_chars:
                    remain = budget_chars - used
                    if remain > 100:
                        parts.append(v[:remain] + "\n...[truncated]")
                        used = budget_chars
                    break
                parts.append(v)
                used += len(v)

        # 4. 死路警告（很小，总是带上）
        if self._dead_ends and used + 200 < budget_chars:
            de = "\n".join(f"- {d}" for d in self._dead_ends[-3:])
            parts.append(f"<avoid_these_failed_strategies>\n{de}\n</avoid_these_failed_strategies>")

        self._stats["assembled_chars"] += used
        return "\n\n".join(parts) if parts else ""

    # ── 观测 ──

    def stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "semantic_keys": list(self._semantic.keys()),
            "semantic_chars": sum(b.char_count for b in self._semantic.values()),
            "episodic_count": len(self._episodic),
            "dead_ends": len(self._dead_ends),
            "hit_rate": (self._stats["cache_hits"]
                          / max(1, self._stats["cache_hits"] + self._stats["cache_misses"])),
        }
