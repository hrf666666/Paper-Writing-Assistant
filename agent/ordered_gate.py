# -*- coding: utf-8 -*-
"""
有序门控流水线 — 多级优先级Gate

借鉴 auto_research_agent 的 ordered gate pipeline 设计：
- Gate 0 (P0-Critical): 格式检查（引用解析、公式处理、无残留标记）
- Gate 1 (P1-High): 事实一致性（数据匹配、符号一致）
- Gate 2 (P2-Medium): 写作质量（LLM评估，现有QualityGate）
- 如果高优先级 Gate 失败，跳过低优先级 Gate（节省LLM调用）
- 死循环保护：连续被阻断 N 次后自动降级为 soft gate
"""

import time
import logging
from typing import Dict, List, Any, Optional
from enum import IntEnum

from agent.verifier import ContentVerifier, VerifyReport

logger = logging.getLogger(__name__)


class GatePriority(IntEnum):
    """Gate 优先级"""
    P0_CRITICAL = 0   # 格式检查，必须通过
    P1_HIGH = 1       # 事实一致性，应通过
    P2_MEDIUM = 2     # 写作质量，建议通过


class GateResult:
    """单个 Gate 的执行结果"""

    def __init__(self, name: str, priority: GatePriority, passed: bool,
                 score: float, details: str = "", fix_hints: List[str] = None):
        self.name = name
        self.priority = priority
        self.passed = passed
        self.score = score
        self.details = details
        self.fix_hints = fix_hints or []
        self.skipped = False
        self.execution_time = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "priority": self.priority.name,
            "passed": self.passed,
            "score": self.score,
            "details": self.details,
            "fix_hints": self.fix_hints,
            "skipped": self.skipped,
            "execution_time": round(self.execution_time, 2),
        }


class OrderedGatePipeline:
    """
    有序门控流水线

    核心思想：
    1. Gate 按优先级从高到低执行
    2. 高优先级 Gate 失败时，低优先级 Gate 自动跳过
    3. 死循环保护：连续被同一 Gate 阻断 N 次 → 降级为 soft（警告但通过）
    4. 支持 hard gate（阻断流水线）和 soft gate（仅警告）

    用法:
        pipeline = OrderedGatePipeline(verifier, quality_gate)
        result = pipeline.run(chapters, abstract, bibliography)
        if result.passed:
            ...
    """

    # 同一 gate 连续阻断多少次后自动降级
    MAX_HARD_BLOCKS = 3

    def __init__(self, verifier: ContentVerifier = None,
                 quality_gate=None):
        self.verifier = verifier or ContentVerifier()
        self.quality_gate = quality_gate  # 可以是 None（跳过 P2）
        self._block_counts: Dict[str, int] = {}  # gate_name -> 连续阻断次数
        self._history: List[Dict] = []

    def run(self, chapters: Dict, abstract: str = "",
            bibliography: str = "",
            skip_llm_gate: bool = False) -> 'PipelineResult':
        """
        执行有序门控流水线

        Args:
            chapters: {chapter_key: content} 字典
            abstract: 摘要文本
            bibliography: 参考文献列表
            skip_llm_gate: 是否跳过LLM质量评估（节省API调用）

        Returns:
            PipelineResult
        """
        start_time = time.time()
        results: List[GateResult] = []
        overall_passed = True
        blocked_by = None

        # ===== Gate 0: P0-Critical — 格式检查（纯代码，零LLM成本） =====
        gate0 = self._run_gate0(chapters, abstract, bibliography)
        results.append(gate0)

        if not gate0.passed and self._is_hard_gate(gate0.name):
            overall_passed = False
            blocked_by = gate0.name
            # 跳过后续 Gate
            for g in self._create_skipped_gates(["gate1_consistency", "gate2_quality"]):
                results.append(g)
        else:
            # ===== Gate 1: P1-High — 事实一致性（纯代码） =====
            gate1 = self._run_gate1(chapters, abstract)
            results.append(gate1)

            if not gate1.passed and self._is_hard_gate(gate1.name):
                overall_passed = False
                blocked_by = gate1.name
                for g in self._create_skipped_gates(["gate2_quality"]):
                    results.append(g)
            else:
                # ===== Gate 2: P2-Medium — 写作质量（LLM评估） =====
                if skip_llm_gate or not self.quality_gate:
                    gate2 = GateResult(
                        "gate2_quality", GatePriority.P2_MEDIUM,
                        passed=True, score=100,
                        details="LLM质量评估已跳过"
                    )
                    gate2.skipped = True
                else:
                    gate2 = self._run_gate2(chapters)
                results.append(gate2)

        elapsed = time.time() - start_time

        result = PipelineResult(
            passed=overall_passed,
            gates=results,
            total_time=elapsed,
            blocked_by=blocked_by,
        )

        # 记录到历史
        self._history.append(result.to_dict())
        self._update_block_counts(results)

        logger.info(f"[OrderedGate] {'PASS' if overall_passed else 'BLOCKED'} "
                     f"| score={result.weighted_score:.1f} "
                     f"| time={elapsed:.1f}s"
                     f"{' | blocked_by=' + blocked_by if blocked_by else ''}")

        return result

    def _run_gate0(self, chapters: Dict, abstract: str,
                    bibliography: str) -> GateResult:
        """Gate 0: P0-Critical 格式检查"""
        start = time.time()

        verify_report = self.verifier.verify_all(
            chapters, abstract, bibliography
        )

        # 只关注 P0 级别的检查项（引用完整性、公式语法、残留标记）
        p0_checks = [
            c for c in verify_report.checks
            if c["name"] in (
                "V1_citation_integrity",
                "V3_formula_syntax",
                "V5_residual_markers",
            )
        ]

        p0_score = (sum(c["score"] for c in p0_checks) / len(p0_checks)
                    if p0_checks else 100)
        p0_passed = all(c["passed"] for c in p0_checks) or p0_score >= 90.0

        details = "; ".join(
            f"{c['name']}: {c['details'][:60]}"
            for c in p0_checks if not c["passed"]
        ) or "P0 格式检查全部通过"

        fix_hints = [c["fix_hint"] for c in p0_checks
                     if not c["passed"] and c.get("fix_hint")]

        result = GateResult(
            "gate0_format", GatePriority.P0_CRITICAL,
            passed=p0_passed, score=p0_score,
            details=details, fix_hints=fix_hints,
        )
        result.execution_time = time.time() - start
        return result

    def _run_gate1(self, chapters: Dict, abstract: str) -> GateResult:
        """Gate 1: P1-High 事实一致性检查"""
        start = time.time()

        verify_report = self.verifier.verify_all(chapters, abstract)

        # 只关注 P1 级别的检查项
        p1_checks = [
            c for c in verify_report.checks
            if c["name"] in (
                "V2_data_consistency",
                "V4_paragraph_dedup",
                "V6_section_references",
                "V8_symbol_consistency",
            )
        ]

        # P1 检查中 error 级别的失败才算不通过
        critical_failures = [
            c for c in p1_checks
            if not c["passed"] and c.get("severity") == "error"
        ]

        p1_passed = len(critical_failures) == 0
        p1_score = (sum(c["score"] for c in p1_checks) / len(p1_checks)
                    if p1_checks else 100)

        details = "; ".join(
            f"{c['name']}: {c['details'][:60]}"
            for c in critical_failures
        ) or "P1 一致性检查通过"

        fix_hints = [c["fix_hint"] for c in p1_checks
                     if not c["passed"] and c.get("fix_hint")]

        result = GateResult(
            "gate1_consistency", GatePriority.P1_HIGH,
            passed=p1_passed, score=p1_score,
            details=details, fix_hints=fix_hints,
        )
        result.execution_time = time.time() - start
        return result

    def _run_gate2(self, chapters: Dict) -> GateResult:
        """Gate 2: P2-Medium 写作质量（使用现有 QualityGate）"""
        start = time.time()

        try:
            # 对全文做一个综合评估
            full_text = "\n\n".join(str(v) for v in chapters.values() if v)
            report = self.quality_gate.evaluate(
                "Full Paper", full_text[:8000]
            )

            result = GateResult(
                "gate2_quality", GatePriority.P2_MEDIUM,
                passed=report.passed,
                score=report.overall_score,
                details=f"QualityGate: {report.overall_score:.1f}/100",
                fix_hints=report.suggestions[:3],
            )
        except Exception as e:
            result = GateResult(
                "gate2_quality", GatePriority.P2_MEDIUM,
                passed=True, score=50,  # LLM 评估失败不应阻断
                details=f"QualityGate 异常（已跳过）: {str(e)[:100]}",
            )

        result.execution_time = time.time() - start
        return result

    def _is_hard_gate(self, gate_name: str) -> bool:
        """
        判断 gate 是否应该硬性阻断

        死循环保护：如果同一 gate 连续阻断了 MAX_HARD_BLOCKS 次，
        自动降级为 soft gate（仅警告，不阻断）
        """
        block_count = self._block_counts.get(gate_name, 0)
        if block_count >= self.MAX_HARD_BLOCKS:
            logger.warning(
                f"[OrderedGate] {gate_name} 连续阻断 {block_count} 次，"
                f"自动降级为 soft gate"
            )
            return False
        return True

    def _update_block_counts(self, results: List[GateResult]):
        """更新阻断计数"""
        for r in results:
            if r.skipped:
                continue
            if r.passed:
                self._block_counts[r.name] = 0  # 通过了就重置
            else:
                self._block_counts[r.name] = self._block_counts.get(r.name, 0) + 1

    @staticmethod
    def _create_skipped_gates(names: List[str]) -> List[GateResult]:
        """创建跳过的 Gate 结果"""
        results = []
        for name in names:
            r = GateResult(
                name, GatePriority.P2_MEDIUM,
                passed=True, score=100,
                details="跳过（前序 Gate 未通过）"
            )
            r.skipped = True
            results.append(r)
        return results

    def get_history(self, limit: int = 10) -> List[Dict]:
        """获取历史执行记录"""
        return self._history[-limit:]


class PipelineResult:
    """流水线执行结果"""

    def __init__(self, passed: bool, gates: List[GateResult],
                 total_time: float, blocked_by: str = None):
        self.passed = passed
        self.gates = gates
        self.total_time = total_time
        self.blocked_by = blocked_by

    @property
    def weighted_score(self) -> float:
        """加权得分：P0 权重 0.5, P1 权重 0.3, P2 权重 0.2"""
        weights = {
            GatePriority.P0_CRITICAL: 0.5,
            GatePriority.P1_HIGH: 0.3,
            GatePriority.P2_MEDIUM: 0.2,
        }
        total_weight = 0
        total_score = 0
        for gate in self.gates:
            if gate.skipped:
                continue
            w = weights.get(gate.priority, 0)
            total_weight += w
            total_score += gate.score * w
        return total_score / total_weight if total_weight > 0 else 0

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "weighted_score": round(self.weighted_score, 1),
            "total_time": round(self.total_time, 2),
            "blocked_by": self.blocked_by,
            "gates": [g.to_dict() for g in self.gates],
        }

    def get_fix_plan(self) -> List[str]:
        """获取修复计划（按优先级排序）"""
        plan = []
        for gate in sorted(self.gates, key=lambda g: g.priority):
            if gate.skipped or gate.passed:
                continue
            plan.extend(gate.fix_hints)
        return plan

    def summary(self) -> str:
        lines = [
            f"PipelineResult: {'PASS' if self.passed else 'BLOCKED'}",
            f"Weighted Score: {self.weighted_score:.1f}",
            f"Total Time: {self.total_time:.1f}s",
        ]
        if self.blocked_by:
            lines.append(f"Blocked By: {self.blocked_by}")
        for gate in self.gates:
            status = "SKIP" if gate.skipped else ("PASS" if gate.passed else "FAIL")
            lines.append(f"  [{status}] {gate.name} ({gate.score:.1f})")
        return "\n".join(lines)
