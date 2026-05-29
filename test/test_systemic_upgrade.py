# -*- coding: utf-8 -*-
"""
单元测试 — 系统性升级的5个新模块

测试覆盖：
1. ContentVerifier (agent/verifier.py)
2. OrderedGatePipeline (agent/ordered_gate.py)
3. BoundedContextManager (agent/bounded_context.py)
4. ChapterStateMachine / PaperStateMachine (agent/chapter_state_machine.py)
5. ToolTrace (agent/tool_trace.py)

运行: cd /home/bigboss/code/paper-writing-assistant && python -m pytest test/test_systemic_upgrade.py -v
"""

import sys
import os
import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==================================================================
# 1. ContentVerifier 测试
# ==================================================================

class TestContentVerifier:
    """测试 VERIFY 独立验证层"""

    def setup_method(self):
        from agent.verifier import ContentVerifier
        self.verifier = ContentVerifier()

    def test_clean_text_passes_all(self):
        """干净的文本应该通过所有检查"""
        chapters = {
            1: "# Introduction\n\nThis paper proposes a novel method for depth estimation.\n\n## Contributions\n\nWe contribute three aspects.",
            2: "# Related Work\n\nPrevious work on light field depth estimation includes LF [1].",
            3: "# Methodology\n\n## Proposed Framework\n\nWe propose a unified framework.\n\nThe loss function $L$ is defined as:\n$$L = L_1 + L_2$$",
            4: "# Experiments\n\n## Evaluation\n\nOur method achieves MAE of 0.52 on dataset A.\n\n## Ablation\n\nWe conduct ablation studies.",
            5: "# Conclusion\n\nIn this paper, we presented a method.",
        }
        abstract = "Our method achieves 0.52 MAE."
        bibliography = "[1] Author, \"Paper Title,\" Conference, 2024."

        report = self.verifier.verify_all(chapters, abstract, bibliography)
        assert report.passed_count >= 5, f"至少5个检查应通过，实际 {report.passed_count}"
        assert report.total_score > 50, f"总分应 > 50，实际 {report.total_score}"

    def test_unresolved_citations_detected(self):
        """[?] 未解析引用应该被检测到"""
        chapters = {1: "Some text with [?] and [?] markers."}
        report = self.verifier.verify_all(chapters)
        v1_check = next((c for c in report.checks if c["name"] == "V1_citation_integrity"), None)
        assert v1_check is not None
        assert not v1_check["passed"], "有 [?] 时 V1 不应通过"

    def test_residual_formula_tags_detected(self):
        """残留 <formula> 标记应被检测到"""
        chapters = {1: "Here is a formula <formula>x^2</formula> and another <formula>."}
        report = self.verifier.verify_all(chapters)
        v3 = next((c for c in report.checks if c["name"] == "V3_formula_syntax"), None)
        assert v3 is not None
        assert not v3["passed"], "有残留 <formula> 时 V3 不应通过"

    def test_residual_markers_detected(self):
        """残留标记应被检测到"""
        chapters = {1: "Text with <citation>something</citation> and [?] and TODO items."}
        report = self.verifier.verify_all(chapters)
        v5 = next((c for c in report.checks if c["name"] == "V5_residual_markers"), None)
        assert v5 is not None
        assert not v5["passed"]

    def test_data_inconsistency_detected(self):
        """Abstract 中不匹配的数值应被检测到"""
        chapters = {
            4: "Experiments show our method achieves 0.52 MAE and 0.38 RMSE.",
        }
        abstract = "Our method achieves 0.99 MAE."
        report = self.verifier.verify_all(chapters, abstract)
        v2 = next((c for c in report.checks if c["name"] == "V2_data_consistency"), None)
        assert v2 is not None
        assert not v2["passed"], "Abstract 数值不匹配时 V2 不应通过"

    def test_data_consistency_passes(self):
        """一致的数值应通过检查"""
        chapters = {
            4: "Our method achieves 0.52 MAE and 0.38 RMSE.",
        }
        abstract = "Our method achieves 0.52 MAE."
        report = self.verifier.verify_all(chapters, abstract)
        v2 = next((c for c in report.checks if c["name"] == "V2_data_consistency"), None)
        assert v2 is not None
        assert v2["passed"], "一致数值时 V2 应通过"

    def test_section_reference_invalid(self):
        """无效的 Section 引用应被检测到"""
        chapters = {
            1: "As described in Section 7, our method...",
        }
        report = self.verifier.verify_all(chapters)
        v6 = next((c for c in report.checks if c["name"] == "V6_section_references"), None)
        assert v6 is not None
        assert not v6["passed"], "Section 7 超出范围时 V6 不应通过"

    def test_chapter_level_verify(self):
        """单章节验证"""
        report = self.verifier.verify_chapter(
            "Introduction",
            "# Introduction\n\nThis paper proposes a method. " * 30
        )
        assert report.passed_count >= 2

    def test_empty_chapter_fails(self):
        """空章节应失败"""
        report = self.verifier.verify_chapter("Introduction", "")
        assert not report.passed

    def test_paragraph_dedup_detects_duplicates(self):
        """段落重复应被检测到"""
        long_para = "This is a very unique paragraph about deep learning methods for light field depth estimation using multi-view stereo matching techniques."
        chapters = {
            1: long_para,
            5: long_para,  # 完全重复
        }
        report = self.verifier.verify_all(chapters)
        v4 = next((c for c in report.checks if c["name"] == "V4_paragraph_dedup"), None)
        assert v4 is not None
        assert not v4["passed"], "段落重复时 V4 不应通过"


# ==================================================================
# 2. OrderedGatePipeline 测试
# ==================================================================

class TestOrderedGatePipeline:
    """测试有序门控流水线"""

    def setup_method(self):
        from agent.verifier import ContentVerifier
        from agent.ordered_gate import OrderedGatePipeline
        self.verifier = ContentVerifier()
        self.pipeline = OrderedGatePipeline(verifier=self.verifier)

    def test_clean_text_passes_pipeline(self):
        """干净文本应通过流水线"""
        chapters = {
            1: "# Introduction\n\nThis paper proposes a novel method.",
            2: "# Related Work\n\nPrevious work [1] is relevant.",
            3: "# Method\n\nWe propose a framework.",
            4: "# Experiments\n\nResults: 0.52 MAE.",
            5: "# Conclusion\n\nWe conclude.",
        }
        abstract = "Results: 0.52 MAE."
        bibliography = "[1] Author, \"Title,\" 2024."

        result = self.pipeline.run(chapters, abstract, bibliography, skip_llm_gate=True)
        assert result.passed, f"流水线应通过: {result.summary()}"
        assert result.weighted_score > 50

    def test_residual_markers_block_pipeline(self):
        """残留标记应阻断流水线"""
        chapters = {
            1: "Text with [?] and <formula> residual.",
        }
        result = self.pipeline.run(chapters, skip_llm_gate=True)
        # 应被 gate0 阻断
        assert result.blocked_by == "gate0_format", f"应被 gate0 阻断: {result.summary()}"

    def test_dead_loop_protection(self):
        """死循环保护：连续阻断后自动降级"""
        # 模拟连续阻断
        self.pipeline._block_counts["gate0_format"] = 3
        chapters = {1: "Text with [?] marker."}
        result = self.pipeline.run(chapters, skip_llm_gate=True)
        # 连续阻断3次后应降级为 soft gate，不再阻断
        # 注意：这里 gate0 实际结果可能仍然不通过，但 should not block
        assert result.blocked_by is None or result.blocked_by == "gate1_consistency"

    def test_pipeline_result_has_fix_plan(self):
        """流水线失败时应提供修复计划"""
        chapters = {1: "Text with [?] markers."}
        result = self.pipeline.run(chapters, skip_llm_gate=True)
        fix_plan = result.get_fix_plan()
        assert isinstance(fix_plan, list)

    def test_pipeline_result_serializable(self):
        """流水线结果应可序列化"""
        chapters = {1: "# Introduction\nSome text."}
        result = self.pipeline.run(chapters, skip_llm_gate=True)
        d = result.to_dict()
        assert "passed" in d
        assert "gates" in d
        assert isinstance(d["gates"], list)


# ==================================================================
# 3. BoundedContextManager 测试
# ==================================================================

class TestBoundedContextManager:
    """测试恒定大小上下文管理器"""

    def setup_method(self):
        from agent.bounded_context import BoundedContextManager
        self.ctx = BoundedContextManager(budget=500)

    def test_context_within_budget(self):
        """上下文应严格在预算内"""
        # 塞入大量数据
        self.ctx.set_project_brief("A" * 1000)
        self.ctx.set_working("outline", "B" * 1000)
        self.ctx.update_short_term({"ch1": "C" * 1000, "ch2": "D" * 1000})

        context = self.ctx.build_prompt_context()
        assert len(context) <= 500, f"上下文应 <= 500，实际 {len(context)}"

    def test_empty_context(self):
        """空上下文应返回空字符串"""
        context = self.ctx.build_prompt_context()
        assert len(context) == 0

    def test_chapter_summary_extraction(self):
        """章节摘要应提取关键信息"""
        content = """# Introduction

## Motivation

Light field depth estimation is important.

## Contributions

We propose three innovations.

Our method achieves 0.52 MAE accuracy on the benchmark.
"""
        self.ctx.update_chapter_summary("1", content)
        summary = self.ctx.get_chapter_summary("1")
        assert len(summary) > 0
        assert len(summary) < len(content)  # 摘要应比原文短

    def test_previous_summaries(self):
        """应能获取前序章节摘要"""
        for i in range(1, 4):
            content = f"# Chapter {i}\n\n" + "This is a detailed chapter summary about deep learning methodology and experimental results. " * 3
            self.ctx.update_chapter_summary(str(i), content)
        summaries = self.ctx.get_previous_summaries(4)
        assert len(summaries) == 3

    def test_symbol_extraction(self):
        """应能提取符号定义"""
        content = "The loss $L$ (total loss) is defined as $L = L_1 + L_2$."
        self.ctx.extract_symbols_from_content(content)
        assert len(self.ctx._symbol_table) > 0

    def test_innovation_points(self):
        """创新点应被存入长期记忆"""
        self.ctx.set_innovation_points([
            {"创新点名称": "Dual-Mask", "创新点价值": "Improved accuracy"},
        ])
        assert "innovations" in self.ctx._long_term
        assert "Dual-Mask" in self.ctx._long_term["innovations"]

    def test_stats(self):
        """统计信息应正确"""
        stats = self.ctx.get_stats()
        assert "total_budget" in stats
        assert stats["total_budget"] == 500


# ==================================================================
# 4. ChapterStateMachine 测试
# ==================================================================

class TestChapterStateMachine:
    """测试章节级状态机"""

    def setup_method(self):
        from agent.chapter_state_machine import ChapterStateMachine
        self.sm = ChapterStateMachine("Introduction", "1")

    def test_initial_state_is_outline(self):
        """初始状态应为 outline"""
        from agent.chapter_state_machine import ChapterPhase
        assert self.sm.phase == ChapterPhase.OUTLINE

    def test_advance_to_draft(self):
        """应能推进到 draft"""
        from agent.chapter_state_machine import ChapterPhase
        result = self.sm.advance("draft", "Draft content...", verify_score=80)
        assert result
        assert self.sm.phase == ChapterPhase.DRAFT

    def test_low_score_blocks_advance(self):
        """低分应阻止推进"""
        from agent.chapter_state_machine import ChapterPhase
        result = self.sm.advance("draft", "Poor content", verify_score=10)
        assert not result
        assert self.sm.phase == ChapterPhase.OUTLINE

    def test_force_complete(self):
        """强制完成应能跳过阶段"""
        self.sm.force_complete("Final content", "max retries reached")
        from agent.chapter_state_machine import ChapterPhase
        assert self.sm.phase == ChapterPhase.FINAL
        assert self.sm.is_complete

    def test_max_retries_force_advance(self):
        """达到最大重试应强制推进"""
        from agent.chapter_state_machine import ChapterPhase
        self.sm.state.max_retries = 2
        # 第一次失败
        self.sm.advance("draft", "bad", verify_score=10)
        # 第二次失败
        self.sm.advance("draft", "still bad", verify_score=10)
        # 第三次应该强制推进
        result = self.sm.advance("draft", "third attempt", verify_score=10)
        assert result  # 强制推进

    def test_history_recorded(self):
        """阶段转换历史应被记录"""
        self.sm.advance("draft", "Draft", verify_score=80)
        history = self.sm.get_history()
        assert len(history) == 1
        assert history[0]["from"] == "outline"
        assert history[0]["to"] == "draft"

    def test_to_dict_serializable(self):
        """应能序列化为字典"""
        d = self.sm.to_dict()
        assert "chapter_name" in d
        assert "current_phase" in d


class TestPaperStateMachine:
    """测试论文级状态机"""

    def setup_method(self):
        from agent.chapter_state_machine import PaperStateMachine
        self.psm = PaperStateMachine()
        self.psm.register_chapter("1", "Introduction")
        self.psm.register_chapter("2", "Related Work")
        self.psm.register_chapter("3", "Methodology")

    def test_get_next_pending(self):
        """应返回第一个未完成的章节"""
        sm = self.psm.get_next_pending()
        assert sm is not None
        assert sm.state.chapter_name == "Introduction"

    def test_progress_tracking(self):
        """进度应正确跟踪"""
        progress = self.psm.progress
        assert progress["total"] == 3
        assert progress["completed"] == 0

        # 完成第一章
        sm = self.psm.get_chapter("1")
        sm.force_complete("Content")

        progress = self.psm.progress
        assert progress["completed"] == 1

    def test_all_complete(self):
        """全部完成检测"""
        assert not self.psm.all_complete
        for key in ["1", "2", "3"]:
            self.psm.get_chapter(key).force_complete("Content")
        assert self.psm.all_complete


# ==================================================================
# 5. ToolTrace 测试
# ==================================================================

class TestToolTrace:
    """测试 ToolTrace 反捏造机制"""

    def setup_method(self):
        from agent.tool_trace import ToolTrace
        self.trace = ToolTrace()

    def test_record_search(self):
        """搜索记录应被正确存储"""
        self.trace.record_search("deep learning", {"data": [{"id": "abc", "title": "Test Paper"}]})
        stats = self.trace.get_stats()
        assert stats["total_searches"] == 1

    def test_record_citation_verified(self):
        """验证的引用应被标记"""
        self.trace.record_citation(
            "Smith et al. 2024", "[1]",
            matched_paper={"title": "Smith Paper"},
            paper_id="xyz",
            verified=True,
            source="reference_pool",
        )
        stats = self.trace.get_stats()
        assert stats["verified_citations"] == 1

    def test_record_citation_unverified(self):
        """未验证的引用应被标记"""
        self.trace.record_citation(
            "Unknown et al.", "[?]",
            verified=False,
            source="unverified",
        )
        stats = self.trace.get_stats()
        assert stats["unverified_citations"] == 1

    def test_verify_claims(self):
        """声明验证应正确统计"""
        self.trace.record_citation("ref1", "[1]", verified=True, source="api")
        self.trace.record_citation("ref2", "[?]", verified=False, source="unverified")

        chapters = {1: "Text with [1] and [?] references."}
        report = self.trace.verify_claims(chapters)
        assert report["verified_citations"] == 1
        assert report["unverified_citations"] == 1

    def test_search_dedup(self):
        """应能检测重复搜索"""
        self.trace.record_search("depth estimation", {"data": []})
        assert self.trace.was_searched("depth estimation")
        assert not self.trace.was_searched("image classification")

    def test_verified_paper_cache(self):
        """已验证论文应被缓存"""
        self.trace.record_search("test", {"data": [{"paperId": "pid1", "title": "Paper1"}]})
        paper = self.trace.get_verified_paper("pid1")
        assert paper is not None
        assert paper["title"] == "Paper1"

    def test_to_dict(self):
        """应能序列化为字典"""
        d = self.trace.to_dict()
        assert "traces" in d
        assert "citations" in d
        assert "stats" in d


# ==================================================================
# 运行入口
# ==================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
