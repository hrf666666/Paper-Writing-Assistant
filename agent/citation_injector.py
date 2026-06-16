# -*- coding: utf-8 -*-
"""
CitationInjector —— 引用上下文构建器（v14 第2步从 loop.py 拆出）

职责：从 reference_pool + citation_bank + FactBase 构建章节 prompt 用的引用上下文。
副作用：构建 cite_key_map / title_to_key（BibTeX 阶段消费），通过属性回写。

原 loop.py 方法：_build_citation_context / _uncached / _build_cite_key_list。
v14 修正：fact_sheet 改用 FactBase.as_fact_sheet()（修 FactBase 半接通断点）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CitationInjector:
    """引用上下文构建器。数据源在构造时注入，cite_key_map/title_to_key 构建后回写到传入的 holder。"""

    def __init__(self, reference_pool: List[Dict], citation_bank: Dict,
                 factbase=None, paper_context: Optional[Dict] = None,
                 memory=None):
        self._reference_pool = reference_pool or []
        self._citation_bank = citation_bank or {}
        self._factbase = factbase
        self._paper_context = paper_context or {}
        self._memory = memory  # LayeredMemory，用于缓存
        # 构建后回写的映射（被 BibTeX 阶段消费）
        self.cite_key_map: Dict[str, Dict] = {}
        self.title_to_key: Dict[str, str] = {}

    def build(self) -> str:
        """构建引用上下文（经 LayeredMemory 缓存）。返回注入 prompt 的字符串。"""
        if self._memory is not None:
            return self._memory.get_or_compute(
                "citation_context",
                depends=[self._citation_bank, self.cite_key_map, self._paper_context,
                         getattr(self._factbase, 'metrics', None)],
                compute=self._build_uncached,
            )
        return self._build_uncached()

    def _build_uncached(self) -> str:
        """构建引用上下文（未缓存版）。"""
        parts = []

        # 1. FactBase 事实清单（v14: 优先用 FactBase.as_fact_sheet，修半接通断点）
        fact_sheet = self._build_fact_sheet()
        if fact_sheet:
            parts.append(fact_sheet)

        # 2. 从 citation_bank 提取可引用的 claim
        if self._citation_bank and self._citation_bank.get("claims"):
            claims = self._citation_bank["claims"][:50]
            claim_lines = []
            for c in claims:
                title = c.get("title", "")
                year = c.get("year", "")
                claim_text = c.get("claim", "")
                if title and claim_text:
                    claim_lines.append(f"  - [{year}] {title}: {claim_text[:150]}")
            if claim_lines:
                parts.append("**Reference claims (use these papers for citations):**")
                parts.append("\n".join(claim_lines[:40]))

        # 3. 生成精确 cite key 列表
        cite_key_block = self._build_cite_key_list()
        if cite_key_block:
            parts.append(cite_key_block)

        if not parts:
            return ""

        instruction = ("\n\n**IMPORTANT**: When citing, "
                       "use \\cite{key} format with keys from the CITE KEY REFERENCE LIST above. "
                       "Do NOT fabricate cite keys not in that list. "
                       "Each chapter must cite at least 5 different references.")
        return "\n\n".join(parts) + instruction

    def _build_fact_sheet(self) -> str:
        """v14: 优先 FactBase.as_fact_sheet()，降级旧 paper_context dict。"""
        if self._factbase and not self._factbase.is_empty():
            return ("**MANDATORY FACT SHEET (FactBase)** — "
                    "Use these exact values. Do NOT invent different numbers:\n"
                    + self._factbase.as_fact_sheet().replace("<fact_base>", "").replace("</fact_base>", "").strip())
        # 降级：旧 paper_context dict（兼容）
        pc = self._paper_context
        if pc and isinstance(pc, dict) and any(pc.values()):
            fact_lines = []
            if pc.get("hardware"):
                fact_lines.append(f"  Hardware: {pc['hardware']}")
            if pc.get("training_params"):
                for k, v in pc["training_params"].items():
                    fact_lines.append(f"  {k}: {v}")
            if pc.get("loss_terms"):
                lt = list(pc['loss_terms']) if not isinstance(pc['loss_terms'], list) else pc['loss_terms']
                fact_lines.append(f"  Loss components: {', '.join(str(t) for t in lt[:6])}")
            if pc.get("datasets"):
                ds = list(pc['datasets']) if not isinstance(pc['datasets'], list) else pc['datasets']
                fact_lines.append(f"  Datasets: {', '.join(str(d) for d in ds[:5])}")
            if pc.get("metrics"):
                metric_lines = [f"    {k}: {v}" for k, v in list(pc["metrics"].items())[:8]]
                fact_lines.append("  Key metrics (use these EXACT values throughout):")
                fact_lines.extend(metric_lines)
            if pc.get("model_name"):
                fact_lines.append(f"  Model name: {pc['model_name']}")
            if pc.get("innovation_names"):
                inn = list(pc['innovation_names']) if not isinstance(pc['innovation_names'], list) else pc['innovation_names']
                fact_lines.append(f"  Innovation components: {', '.join(str(n) for n in inn[:5])}")
            if fact_lines:
                return ("**MANDATORY FACT SHEET (PaperContext)** — "
                        "Use these exact values. Do NOT invent different numbers:\n"
                        + "\n".join(fact_lines))
        return ""

    def _build_cite_key_list(self) -> str:
        """构建统一的 cite key → paper 映射（单一真相源）。回写 cite_key_map/title_to_key。"""
        from tools.text_utils import generate_bib_key

        self.cite_key_map = {}
        self.title_to_key = {}
        entries = {}

        seen_titles = set()
        all_sources = []
        for p in self._reference_pool:
            t = p.get("title", "").lower().strip()
            if t and t not in seen_titles:
                all_sources.append(p)
                seen_titles.add(t)
        if self._citation_bank and self._citation_bank.get("claims"):
            for c in self._citation_bank["claims"]:
                t = c.get("title", "").lower().strip()
                if t and t not in seen_titles:
                    all_sources.append(c)
                    seen_titles.add(t)

        for p in all_sources:
            title = p.get("title", "")
            if not title:
                continue
            authors = p.get("authors", [])
            year = str(p.get("year", ""))
            base_key = generate_bib_key(authors, year, title)

            key = base_key
            suffix = 2
            while key in self.cite_key_map:
                existing = self.cite_key_map[key]
                if existing.get("title", "").lower().strip() == title.lower().strip():
                    break
                key = f"{base_key}_{suffix}"
                suffix += 1

            if key not in self.cite_key_map:
                venue = p.get("venue_abbr", "") or p.get("venue", "")
                if isinstance(venue, dict):
                    venue = venue.get("raw", "")
                venue_str = f", {venue}" if venue else ""
                entries[key] = f"{title[:80]} ({year}{venue_str})"
                self.cite_key_map[key] = p
                self.title_to_key[title.lower().strip()] = key

        if not entries:
            return ""

        lines = [f"  \\cite{{{key}}} — {desc}" for key, desc in entries.items()]
        return (
            "**CITE KEY REFERENCE LIST** — Use these EXACT \\cite{key} commands in your LaTeX output. "
            "Do NOT fabricate cite keys not in this list:\n"
            + "\n".join(lines[:60])
        )
