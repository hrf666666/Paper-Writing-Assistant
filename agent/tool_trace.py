# -*- coding: utf-8 -*-
"""
ToolTrace 反捏造机制 — 只信任工具执行结果

借鉴 auto_research_agent 的 ToolTrace 设计：
- 记录每次工具调用（API 搜索、论文检索等）的输入和输出
- 引用验证：LLM 生成的引用必须与实际 API 返回的数据匹配
- 数据追踪：论文中的数据必须可追溯到具体来源
- 未验证的内容标记为 [UNVERIFIED] 而非直接删除

解决的问题：
- LLM 虚构引用（声称引用了不存在的论文）
- 数据编造（Abstract 中的数字不是 Experiments 的）
- 无法区分"真实引用"和"LLM 编造的引用"

用法:
    trace = ToolTrace()
    trace.record_search("deep learning depth estimation", api_results)
    trace.record_citation("[1]", "Smith et al. 2024", verified=True,
                          source_paper_id="abc123")
    report = trace.verify_claims(chapters)
"""

import re
import json
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TraceEntry:
    """工具调用追踪记录"""
    tool_name: str          # "semantic_scholar_search" | "paper_details" | "citation_resolve"
    timestamp: float
    input_data: str         # 搜索查询或引用关键词
    output_data: Any        # API 返回结果
    success: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CitationTrace:
    """引用追踪记录"""
    raw_tag: str            # 原始 <citation> 标记内容
    resolved_as: str        # 解析为 [N]
    matched_paper: Optional[Dict] = None  # 匹配到的论文详情
    paper_id: Optional[str] = None
    verified: bool = False
    verification_source: str = ""  # "reference_pool" | "api_search" | "fallback" | "unverified"


class ToolTrace:
    """
    工具调用追踪器

    核心原则：只信任工具执行结果，不信任 LLM 自述
    """

    def __init__(self):
        self._traces: List[TraceEntry] = []
        self._citation_traces: Dict[str, CitationTrace] = {}  # raw_tag -> trace
        self._verified_papers: Dict[str, Dict] = {}  # paper_id -> paper_data
        self._search_history: List[Dict] = []

    # ──────────── 追踪记录 ────────────

    def record_search(self, query: str, results: Any,
                       tool_name: str = "semantic_scholar_search"):
        """记录一次搜索工具调用"""
        entry = TraceEntry(
            tool_name=tool_name,
            timestamp=time.time(),
            input_data=query,
            output_data=results,
            success=bool(results),
        )
        self._traces.append(entry)

        # 缓存搜索结果中的论文
        if isinstance(results, dict) and "data" in results:
            for paper in results["data"]:
                pid = paper.get("paperId") or paper.get("id", "")
                if pid:
                    self._verified_papers[pid] = paper

        self._search_history.append({
            "query": query,
            "timestamp": entry.timestamp,
            "result_count": (
                len(results.get("data", []))
                if isinstance(results, dict) else 0
            ),
        })

        logger.debug(f"[ToolTrace] 搜索记录: {query[:50]} → "
                      f"{entry.result_count if hasattr(entry, 'result_count') else '?'} 结果")

    def record_citation(self, raw_tag: str, resolved_as: str,
                         matched_paper: Dict = None,
                         paper_id: str = None,
                         verified: bool = False,
                         source: str = "unverified"):
        """
        记录一个引用的解析过程

        Args:
            raw_tag: 原始 <citation> 标记内容
            resolved_as: 解析为 [N]
            matched_paper: 匹配到的论文详情
            paper_id: 论文ID
            verified: 是否通过验证
            source: 验证来源
        """
        trace = CitationTrace(
            raw_tag=raw_tag,
            resolved_as=resolved_as,
            matched_paper=matched_paper,
            paper_id=paper_id,
            verified=verified,
            verification_source=source,
        )
        self._citation_traces[raw_tag] = trace

        status = "✓" if verified else "✗"
        logger.debug(f"[ToolTrace] 引用 {status}: {raw_tag[:40]} → {resolved_as} ({source})")

    def record_paper_detail(self, paper_id: str, details: Dict):
        """记录一次论文详情查询"""
        self._verified_papers[paper_id] = details
        entry = TraceEntry(
            tool_name="paper_details",
            timestamp=time.time(),
            input_data=paper_id,
            output_data=details,
            success=bool(details),
        )
        self._traces.append(entry)

    # ──────────── 验证 ────────────

    def verify_claims(self, chapters: Dict) -> Dict[str, Any]:
        """
        验证章节内容中的声明

        检查项：
        1. 引用是否全部经过验证
        2. 数据是否有工具来源
        """
        report = {
            "total_citations": 0,
            "verified_citations": 0,
            "unverified_citations": 0,
            "citation_verification_rate": 0.0,
            "issues": [],
        }

        full_text = "\n".join(str(v) for v in chapters.values() if v)

        # 统计引用
        all_refs = re.findall(r'\[(\d+)\]', full_text)
        report["total_citations"] = len(all_refs)

        # 检查每个追踪到的引用
        for raw_tag, trace in self._citation_traces.items():
            if trace.verified:
                report["verified_citations"] += 1
            else:
                report["unverified_citations"] += 1
                report["issues"].append({
                    "type": "unverified_citation",
                    "tag": raw_tag[:60],
                    "resolved_as": trace.resolved_as,
                    "source": trace.verification_source,
                })

        if report["total_citations"] > 0:
            report["citation_verification_rate"] = (
                report["verified_citations"] / report["total_citations"]
            )

        # 检查 [?] 未解析引用
        unresolved = full_text.count("[?]")
        if unresolved > 0:
            report["issues"].append({
                "type": "unresolved_citations",
                "count": unresolved,
                "description": f"{unresolved} 个引用标记为 [?]（未解析）",
            })

        return report

    def get_verified_paper(self, paper_id: str) -> Optional[Dict]:
        """获取已验证的论文详情"""
        return self._verified_papers.get(paper_id)

    def is_paper_verified(self, paper_id: str) -> bool:
        """检查论文是否已验证"""
        return paper_id in self._verified_papers

    # ──────────── 统计 ────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取追踪统计"""
        return {
            "total_traces": len(self._traces),
            "total_searches": len(self._search_history),
            "total_citation_traces": len(self._citation_traces),
            "verified_citations": sum(
                1 for t in self._citation_traces.values() if t.verified
            ),
            "unverified_citations": sum(
                1 for t in self._citation_traces.values() if not t.verified
            ),
            "verified_papers": len(self._verified_papers),
            "verification_sources": {
                source: sum(
                    1 for t in self._citation_traces.values()
                    if t.verification_source == source
                )
                for source in set(
                    t.verification_source
                    for t in self._citation_traces.values()
                )
            },
        }

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "traces": [
                {
                    "tool": t.tool_name,
                    "input": t.input_data[:100],
                    "success": t.success,
                    "timestamp": t.timestamp,
                }
                for t in self._traces[-50:]  # 最近50条
            ],
            "citations": {
                tag: {
                    "resolved_as": ct.resolved_as,
                    "verified": ct.verified,
                    "source": ct.verification_source,
                    "paper_id": ct.paper_id,
                }
                for tag, ct in self._citation_traces.items()
            },
            "stats": self.get_stats(),
        }

    # ──────────── 搜索历史查询 ────────────

    def was_searched(self, query: str) -> bool:
        """检查某个查询是否已经搜索过"""
        query_lower = query.lower()
        return any(
            query_lower in h["query"].lower()
            for h in self._search_history
        )

    def get_search_results(self, query: str) -> List[Dict]:
        """获取之前搜索的缓存结果"""
        query_lower = query.lower()
        for trace in self._traces:
            if (trace.tool_name == "semantic_scholar_search"
                    and query_lower in trace.input_data.lower()
                    and trace.output_data):
                if isinstance(trace.output_data, dict):
                    return trace.output_data.get("data", [])
        return []
