# -*- coding: utf-8 -*-
"""
Finding 契约 + FindingBus —— 统一问题数据结构 (v13 PR4)

痛点：7 套不兼容的 issue 结构（auditor 用 category、verifier 用 name+passed、
quality 用 dimension、cross_chapter 用 type、constraint 用 rule）→ 无法合并、
无法互读、审计结果写盘即丢。

本模块定义统一的 Finding 类型 + FindingBus 收集/查询中枢。
旧子系统通过 to_findings() 适配器接入，不改内部逻辑。

Finding vs 旧 issue 的映射：
  auditor.AuditIssue    → Finding(source="auditor", kind=category, evidence, fix=suggestion)
  verifier.check        → Finding(source="verifier", kind=name, severity by passed)
  quality issue         → Finding(source="quality", kind=dimension, location)
  cross_chapter issue   → Finding(source="cross_chapter", kind=type)
  Violation             → Finding(source="constraint", kind=rule, fix_hint)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    """统一严重度（字符串枚举，可比较可序列化）。"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Location:
    """结构化定位。任一字段可空。"""
    chapter: Optional[str] = None     # "ch3" / "abstract" / "main.tex"
    section: Optional[str] = None     # "3.2"
    char_span: Optional[Tuple[int, int]] = None  # 文本内 (start, end)
    line: Optional[int] = None        # tex 行号
    raw: str = ""                     # 原始位置串（旧子系统透传）

    def __str__(self) -> str:
        parts = []
        if self.chapter:
            parts.append(self.chapter)
        if self.section:
            parts.append(self.section)
        if self.line is not None:
            parts.append(f"L{self.line}")
        if self.raw and not parts:
            parts.append(self.raw)
        return ":".join(parts) if parts else "(unknown)"


@dataclass
class FixAction:
    """结构化修复动作（可选）。auto_apply=True 可自动执行（如数字替换）。"""
    op: str            # "replace_text"|"replace_number"|"insert_cite"|"regenerate"|"rerender_figure"
    target: str        # 定位锚（文本片段/数值/fig_id）
    replacement: str = ""
    auto_apply: bool = False
    hint: str = ""     # 给 LLM 的人类可读提示

    def __str__(self) -> str:
        return f"{self.op}({self.target!r} → {self.replacement!r})"


@dataclass
class Finding:
    """统一问题/发现。所有子系统的问题都归一为此类型。"""
    source: str                       # "auditor"|"verifier"|"quality"|"cross_chapter"|"constraint"|"latex"|"figure"
    kind: str                         # 来源前缀化的分类："citation:missing"|"number:mismatch"|...
    severity: Severity
    description: str
    location: Location = field(default_factory=Location)
    evidence: str = ""
    fix: Optional[FixAction] = None

    # 自增 id（FindingBus 分配）
    id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id, "source": self.source, "kind": self.kind,
            "severity": self.severity.value, "description": self.description,
            "location": str(self.location) or None,
            "evidence": self.evidence or None,
        }
        if self.fix:
            d["fix"] = {"op": self.fix.op, "target": self.fix.target,
                        "replacement": self.fix.replacement,
                        "auto_apply": self.fix.auto_apply}
        return d


# ──────────────────────────────────────────────────────────────
# FindingBus —— 收集/查询中枢
# ──────────────────────────────────────────────────────────────

class FindingBus:
    """所有子系统发现的 Finding 汇聚于此，供查询/回流/报告。

    用法：
        bus = FindingBus()
        bus.record(finding)
        bus.record_many(findings)
        crit = bus.by(chapter="ch3", severity=Severity.CRITICAL)
        brief = bus.as_revision_brief("ch3")   # 给重写 prompt 用
    """

    def __init__(self):
        self._findings: List[Finding] = []
        self._counter = 0

    def _next_id(self, source: str) -> str:
        self._counter += 1
        return f"{source}-{self._counter:04d}"

    # ── 写 ──

    def record(self, finding: Finding) -> Finding:
        if not finding.id:
            finding.id = self._next_id(finding.source)
        self._findings.append(finding)
        return finding

    def record_many(self, findings: List[Finding]) -> List[Finding]:
        return [self.record(f) for f in findings]

    def clear(self, source: Optional[str] = None):
        """清空（可按来源）。重审某章时用 clear(source='quality')。"""
        if source:
            self._findings = [f for f in self._findings if f.source != source]
        else:
            self._findings.clear()

    # ── 查 ──

    def all(self) -> List[Finding]:
        return list(self._findings)

    def by(self, source: Optional[str] = None, chapter: Optional[str] = None,
           severity: Optional[Severity] = None, kind_prefix: Optional[str] = None,
           ) -> List[Finding]:
        """多维度过滤。"""
        out = []
        for f in self._findings:
            if source and f.source != source:
                continue
            if chapter and f.location.chapter != chapter:
                continue
            if severity and f.severity != severity:
                continue
            if kind_prefix and not f.kind.startswith(kind_prefix):
                continue
            out.append(f)
        return out

    def has_critical(self, chapter: Optional[str] = None) -> bool:
        return bool(self.by(chapter=chapter, severity=Severity.CRITICAL))

    def counts_by_severity(self) -> Dict[str, int]:
        c = defaultdict(int)
        for f in self._findings:
            c[f.severity.value] += 1
        return dict(c)

    # ── 回流：压成修订简报 ──

    def as_revision_brief(self, chapter: Optional[str] = None,
                          max_chars: int = 1500) -> str:
        """把某章的 critical/warning findings 压成 ≤max_chars 反馈，注入重写 prompt。

        优先级：critical > warning；每个 finding 带 location + evidence + fix.hint。
        """
        sev_order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}
        cands = self.by(chapter=chapter)
        cands = [f for f in cands if f.severity in (Severity.CRITICAL, Severity.WARNING)]
        cands.sort(key=lambda f: sev_order.get(f.severity, 9))

        lines = ["<revision_feedback>  # 以下是审查发现的问题，必须针对性修正"]
        used = 0
        for f in cands:
            entry = f"[{f.severity.value.upper()}][{f.source}:{f.kind}] {f.description}"
            if f.location and str(f.location) != "(unknown)":
                entry += f"  @ {f.location}"
            if f.evidence:
                entry += f"  证据: {f.evidence[:80]}"
            if f.fix and f.fix.hint:
                entry += f"  建议: {f.fix.hint[:80]}"
            entry += "\n"
            if used + len(entry) > max_chars:
                lines.append(f"...（还有 {len(cands) - len(lines) + 1} 条问题未列出）")
                break
            lines.append(entry)
            used += len(entry)
        lines.append("</revision_feedback>")
        return "\n".join(lines) if len(lines) > 2 else ""

    def summary(self) -> str:
        c = self.counts_by_severity()
        src = defaultdict(int)
        for f in self._findings:
            src[f.source] += 1
        src_s = ", ".join(f"{k}:{v}" for k, v in sorted(src.items()))
        return (f"FindingBus: {len(self._findings)} 条 "
                f"(critical={c.get('critical',0)}, warning={c.get('warning',0)}, "
                f"info={c.get('info',0)}) | 来源: {src_s}")


# ──────────────────────────────────────────────────────────────
# 适配器：旧子系统 → List[Finding]（不改旧子系统内部逻辑）
# ──────────────────────────────────────────────────────────────

def _norm_severity(s: Any) -> Severity:
    """把各子系统的严重度串归一到 Severity。"""
    if isinstance(s, Severity):
        return s
    s = str(s).lower()
    if s in ("critical", "error", "fatal"):
        return Severity.CRITICAL
    if s in ("warning", "warn"):
        return Severity.WARNING
    return Severity.INFO


def _parse_location(raw: str, chapter_hint: Optional[str] = None) -> Location:
    """从旧子系统的位置串尽量解析。"""
    raw = str(raw or "")
    loc = Location(raw=raw)
    # 识别 chapter
    for ch in ("ch1", "ch2", "ch3", "ch4", "ch5", "abstract", "main.tex"):
        if ch in raw:
            loc.chapter = ch
            break
    if not loc.chapter and chapter_hint:
        loc.chapter = chapter_hint
    return loc


# ── auditor.AuditReport → Findings ──

def audit_report_to_findings(audit_report, chapter_hint: Optional[str] = None) -> List[Finding]:
    """适配 agent/auditor.py 的 AuditReport。"""
    out = []
    issues = getattr(audit_report, "issues", None) or []
    for iss in issues:
        sev = getattr(iss, "severity", "info")
        cat = getattr(iss, "category", "unknown")
        desc = getattr(iss, "description", "")
        loc_raw = getattr(iss, "location", "")
        evid = getattr(iss, "evidence", "")
        sug = getattr(iss, "suggestion", "")
        fix = FixAction(op="regenerate", target=loc_raw, hint=sug) if sug else None
        out.append(Finding(
            source="auditor",
            kind=f"{cat}" if ":" not in cat else cat,
            severity=_norm_severity(sev),
            description=desc,
            location=_parse_location(loc_raw, chapter_hint),
            evidence=evid,
            fix=fix,
        ))
    return out


# ── cross_chapter_checker issues (list[dict]) → Findings ──

def cross_chapter_issues_to_findings(issues: List[Dict],
                                      chapter_hint: Optional[str] = None) -> List[Finding]:
    """适配 agent/cross_chapter_checker.py 的 self.issues (list of dict)。"""
    out = []
    for d in issues:
        typ = d.get("type", "unknown")
        sev = d.get("severity", "warning")
        desc = d.get("description", "")
        loc_raw = d.get("location", "")
        # 数值修复带 old/new → 构造可自动执行的 FixAction
        fix = None
        if "old" in d and "new" in d:
            fix = FixAction(op="replace_number", target=str(d["old"]),
                            replacement=str(d["new"]), auto_apply=True)
        out.append(Finding(
            source="cross_chapter",
            kind=typ,
            severity=_norm_severity(sev),
            description=desc,
            location=_parse_location(loc_raw, chapter_hint),
            fix=fix,
        ))
    return out


# ── latex_constraint Violation → Findings ──

def violations_to_findings(violations, chapter_hint: str = "main.tex") -> List[Finding]:
    """适配 tools/latex_constraint_checker.py 的 Violation 列表。"""
    out = []
    for v in violations:
        rule = getattr(v, "rule", "unknown")
        sev = getattr(v, "severity", "warning")
        desc = getattr(v, "description", "")
        loc_raw = getattr(v, "location", "")
        hint = getattr(v, "fix_hint", "")
        fix = FixAction(op="regenerate", target=loc_raw, hint=hint) if hint else None
        out.append(Finding(
            source="constraint",
            kind=f"latex:{rule}" if ":" not in rule else rule,
            severity=_norm_severity(sev),
            description=desc,
            location=_parse_location(loc_raw, chapter_hint),
            fix=fix,
        ))
    return out


# ── quality_gate issues (list[dict]) → Findings ──

def quality_issues_to_findings(issues: List[Dict],
                                chapter_hint: Optional[str] = None) -> List[Finding]:
    """适配 agent/quality_gate.py 的 QualityReport.issues (list of dict)。"""
    out = []
    for d in issues:
        dim = d.get("dimension", "unknown")
        desc = d.get("description", "")
        loc_raw = d.get("location", "")
        out.append(Finding(
            source="quality",
            kind=f"quality:{dim}" if ":" not in dim else dim,
            severity=_norm_severity(d.get("severity", "warning")),
            description=desc,
            location=_parse_location(loc_raw, chapter_hint),
        ))
    return out
