# -*- coding: utf-8 -*-
"""
Agent 内核 (v13) — 系统的契约层。

四块契约 + 错误分级，是 audit/constraint/guidance/eval/iteration/memory
协作的共同语言。旧模块通过适配器接入，不改内部逻辑。

契约：
    errors   — 错误分级 (Transient/Permanent/DegradedResult) + classify() 闸口
    finding  — 统一问题数据结构 (Finding/FindingBus)          [PR4]
    factbase — 单一事实源 (FactBase)                            [PR2]
    memory   — 分层记忆 (LayeredMemory)                         [PR3]

本包自身不依赖 agent 其他模块（零循环依赖），可被任意层 import。
"""

from agent.core.errors import (
    TransientError,
    PermanentError,
    AllProvidersExhausted,
    DegradedResult,
    classify,
    to_transient,
    to_permanent,
    is_transient,
    should_retry,
)
from agent.core.factbase import (
    FactBase,
    build_from_project_data as build_factbase,
    save as save_factbase,
    load as load_factbase,
    exists as factbase_exists,
)
from agent.core.memory import LayeredMemory
from agent.core.finding import (
    Finding, FindingBus, Severity, Location, FixAction,
    audit_report_to_findings, cross_chapter_issues_to_findings,
    violations_to_findings, quality_issues_to_findings,
)
from agent.core.figure_manifest import (
    FigureManifest, FigureEntry, FigType, FigStatus,
)

__all__ = [
    # errors
    "TransientError", "PermanentError", "AllProvidersExhausted",
    "DegradedResult",
    "classify", "to_transient", "to_permanent",
    "is_transient", "should_retry",
    # factbase
    "FactBase", "build_factbase", "save_factbase",
    "load_factbase", "factbase_exists",
    # memory
    "LayeredMemory",
    # finding
    "Finding", "FindingBus", "Severity", "Location", "FixAction",
    "audit_report_to_findings", "cross_chapter_issues_to_findings",
    "violations_to_findings", "quality_issues_to_findings",
    # figure
    "FigureManifest", "FigureEntry", "FigType", "FigStatus",
]
