# -*- coding: utf-8 -*-
"""
FigureManifest —— 图的单一真相源 + 文图联动 (v13 PR6)

痛点（codereview 实测）：
  - 全文只有 1 张图（架构图），且它走 ch3 的旁路，与 figure_planner 的 teaser 重复且无对账
  - figure_planner 不看章节结构，不知道哪节需要图
  - 无 caption↔章节验证；注入靠正则切 figure 块（双重注入 bug）
  - 占位图/失败图可能混进正文

设计：结构化的图清单（dataclass），替代裸字符串 figure_latex_snippets。
注入正文前按规则筛选+组合，是"单一真相源"原则在图域的应用。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FigStatus(str, Enum):
    PLANNED = "planned"        # 已规划，未渲染
    RENDERED = "rendered"      # 已渲染出 PDF
    VALIDATED = "validated"    # 已通过视觉评价
    FAILED = "failed"          # 渲染失败
    PLACEHOLDER = "placeholder"  # 占位图（不得进正文）


class FigType(str, Enum):
    TEASER = "teaser"              # 总览图（Introduction）
    ARCHITECTURE = "architecture"  # 架构图（Methodology）
    MODULE_DETAIL = "module_detail"
    ABLATION = "ablation"          # 消融数据图
    COMPARISON = "comparison"      # SOTA 对比图
    QUALITATIVE = "qualitative"    # 定性对比


# 图类型 → 该图服务的章节（决定 belongs_to_section 默认值）
_TYPE_TO_SECTION = {
    FigType.TEASER: "1",          # Introduction
    FigType.ARCHITECTURE: "3",    # Methodology
    FigType.MODULE_DETAIL: "3",
    FigType.ABLATION: "4",        # Experiments
    FigType.COMPARISON: "4",
    FigType.QUALITATIVE: "4",
}


@dataclass
class FigureEntry:
    """单张图的完整记录。"""
    fig_id: str                              # "fig_arch" / "fig_ablation"
    fig_type: FigType
    source_pdf: str = ""                     # 渲染出的 PDF 路径（空=未渲染）
    caption: str = ""
    label: str = ""                          # \label{fig:xxx}
    belongs_to_section: str = ""             # "3.2"
    supports_claim: str = ""                 # 该图佐证的论点
    status: FigStatus = FigStatus.PLANNED
    quality_score: float = 0.0               # 视觉评价 0-10
    size_type: str = "double"                # "single"|"double"|"teaser"
    is_placeholder: bool = False
    # 子图组合（当一张大图由多张子图拼成时）
    subfigures: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["fig_type"] = self.fig_type.value
        d["status"] = self.status.value
        return d


class FigureManifest:
    """图清单中枢。注入正文前的筛选/组合都在这里做（确定性规则，不靠 LLM）。"""

    # 质量门槛：低于此分的图不进正文
    MIN_QUALITY = 6.0

    def __init__(self):
        self._entries: List[FigureEntry] = []
        self._by_id: Dict[str, FigureEntry] = {}

    # ── 写 ──

    def add(self, entry: FigureEntry) -> FigureEntry:
        if not entry.belongs_to_section:
            entry.belongs_to_section = _TYPE_TO_SECTION.get(entry.fig_type, "")
        if not entry.label:
            entry.label = f"fig:{entry.fig_id}"
        self._entries.append(entry)
        self._by_id[entry.fig_id] = entry
        return entry

    def update(self, fig_id: str, **kwargs):
        e = self._by_id.get(fig_id)
        if not e:
            return
        for k, v in kwargs.items():
            if hasattr(e, k):
                setattr(e, k, v)

    # ── 查 ──

    def all(self) -> List[FigureEntry]:
        return list(self._entries)

    def get(self, fig_id: str) -> Optional[FigureEntry]:
        return self._by_id.get(fig_id)

    def by_section(self, section: str) -> List[FigureEntry]:
        return [e for e in self._entries if e.belongs_to_section and section in e.belongs_to_section]

    # ── 筛选：哪些图可用进正文（确定性规则）──

    def usable_for_injection(self) -> List[FigureEntry]:
        """返回可注入正文的图（排除失败/占位/低质/重复）。"""
        usable = []
        seen_claims = set()
        for e in self._entries:
            # 规则1: 状态必须 RENDERED 或 VALIDATED
            if e.status not in (FigStatus.RENDERED, FigStatus.VALIDATED):
                continue
            # 规则2: 占位图硬排除
            if e.is_placeholder or e.status == FigStatus.PLACEHOLDER:
                continue
            # 规则3: 无 PDF 路径排除
            if not e.source_pdf:
                continue
            # 规则4: 质量分门槛（VALIDATED 才有分；RENDERED 暂放行）
            if e.status == FigStatus.VALIDATED and e.quality_score < self.MIN_QUALITY:
                logger.info(f"[FigureManifest] 排除 {e.fig_id}: 质量分 {e.quality_score} < {self.MIN_QUALITY}")
                continue
            # 规则5: 同一论点多图 → 取质量最高（其余入 appendix 概念，这里跳过）
            claim_key = e.supports_claim.strip().lower()
            if claim_key and claim_key in seen_claims:
                # 找已选中的同 claim 图，保留分数高的
                existing = next((u for u in usable if u.supports_claim.strip().lower() == claim_key), None)
                if existing and e.quality_score > existing.quality_score:
                    usable.remove(existing)
                else:
                    continue
            if claim_key:
                seen_claims.add(claim_key)
            usable.append(e)
        return usable

    # ── 组合：何时拼图 ──

    def should_compose_subfigures(self, entries: List[FigureEntry]) -> bool:
        """判断是否需要把多张图组合（如消融子图 → 一张大图）。

        规则：同 section + 同 type(qualitative/ablation) + 数量 2-4 → 组合。
        """
        if not entries:
            return False
        types = {e.fig_type for e in entries}
        sections = {e.belongs_to_section for e in entries}
        return (len(types) == 1
                and len(sections) == 1
                and entries[0].fig_type in (FigType.QUALITATIVE, FigType.ABLATION)
                and 2 <= len(entries) <= 4)

    # ── 生成 LaTeX（从结构化清单，而非裸字符串拼接）──

    def to_latex_snippets(self) -> str:
        """把可注入的图渲染为 LaTeX figure 环境（替代旧裸字符串拼接）。

        组合用 \subfloat，不把光栅图用 matplotlib 合成（保留矢量）。
        """
        usable = self.usable_for_injection()
        if not usable:
            return ""
        # 按 section 分组
        from collections import defaultdict
        by_sec = defaultdict(list)
        for e in usable:
            by_sec[e.belongs_to_section or "?"].append(e)

        snippets = []
        for section, entries in by_sec.items():
            if self.should_compose_subfigures(entries):
                snippets.append(self._compose_subfloat(entries))
            else:
                for e in entries:
                    snippets.append(self._single_figure(e))
        return "\n\n".join(snippets)

    def _single_figure(self, e: FigureEntry) -> str:
        env = "figure*" if e.size_type in ("double", "teaser") else "figure"
        width = r"\textwidth" if env == "figure*" else r"\columnwidth"
        return (f"\\begin{{{env}}}[!t]\n"
                f"\\centering\n"
                f"\\includegraphics[width={width}]{{{e.source_pdf}}}\n"
                f"\\caption{{{e.caption}}}\n"
                f"\\label{{{e.label}}}\n"
                f"\\end{{{env}}}")

    def _compose_subfloat(self, entries: List[FigureEntry]) -> str:
        """用 subfloat 组合多子图（保留各自独立 caption + 矢量）。"""
        env = "figure*"
        lines = [f"\\begin{{{env}}}[!t]", "\\centering",
                 "\\usepackage{subfloat}  % 需在 preamble 声明"]
        for i, e in enumerate(entries):
            sub_label = f"{e.label}_sub{i+1}"
            lines.append(f"\\subfloat[{e.caption[:60]}]{{"
                         f"\\includegraphics[width=0.48\\textwidth]{{{e.source_pdf}}}"
                         f"\\label{{{sub_label}}}}}")
        # 主 caption 取第一个的 supports_claim 或通用
        main_cap = entries[0].supports_claim or "Composite figure."
        lines.append(f"\\caption{{{main_cap}}}")
        lines.append(f"\\label{{{entries[0].label}}}")
        lines.append(f"\\end{{{env}}}")
        return "\n".join(lines)

    # ── 文图联动验证 ──

    def validate_linkage(self, tex_content: str) -> List[str]:
        """验证正文 \ref{fig:X} 都有对应 manifest 条目；返回缺失列表。"""
        import re
        refs = set(re.findall(r'\\ref\{fig:([^}]+)\}', tex_content))
        manifest_labels = {e.label.replace("fig:", "") for e in self._entries}
        missing = sorted(refs - manifest_labels)
        return missing

    # ── 持久化 + 统计 ──

    def summary(self) -> Dict[str, Any]:
        from collections import Counter
        status_c = Counter(e.status.value for e in self._entries)
        type_c = Counter(e.fig_type.value for e in self._entries)
        return {
            "total": len(self._entries),
            "by_status": dict(status_c),
            "by_type": dict(type_c),
            "usable_for_injection": len(self.usable_for_injection()),
        }
