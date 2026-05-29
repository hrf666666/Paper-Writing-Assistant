# -*- coding: utf-8 -*-
"""
测试 agent/citation_manager.py - 引用管理器
"""

import pytest
from unittest.mock import MagicMock, patch

from agent.citation_manager import CitationManager


class TestCitationManagerInit:
    """测试 CitationManager 初始化"""

    def test_init_default(self):
        mgr = CitationManager()
        assert mgr._citation_pool == []
        assert mgr._citation_map == {}
        assert mgr._ref_entries == []

    def test_init_with_api_client(self, mock_api_client):
        mgr = CitationManager(api_client=mock_api_client)
        assert mgr.api_client is mock_api_client


class TestCollect:
    """测试 citation 收集"""

    def test_collect_multiple_citations(self):
        mgr = CitationManager()
        text = (
            "See <citation>Smith et al., 2023</citation> for details. "
            "Also <citation>Jones, 2022</citation> supports this."
        )
        citations = mgr.collect(text)
        assert len(citations) == 2
        assert citations[0]["raw_tag"] == "Smith et al., 2023"
        assert citations[1]["raw_tag"] == "Jones, 2022"

    def test_collect_no_citations(self):
        mgr = CitationManager()
        citations = mgr.collect("No citations here.")
        assert citations == []

    def test_collect_preserves_index(self):
        mgr = CitationManager()
        text = "<citation>A</citation> <citation>B</citation> <citation>C</citation>"
        citations = mgr.collect(text)
        assert [c["index"] for c in citations] == [0, 1, 2]


class TestVerify:
    """测试引用验证"""

    def test_verify_with_reference_pool_match(self):
        mgr = CitationManager()
        citations = [{"keywords": [["deep learning"]], "raw_tag": "deep learning survey"}]
        pool = [{"title": "Deep Learning Survey", "paperId": "p1", "authors": []}]

        verified = mgr.verify(citations, reference_pool=pool)
        assert len(verified) == 1
        assert verified[0]["verified"] is True
        assert verified[0]["paper_id"] == "p1"

    @patch("api.paper_search.verify_citation_with_mcp", return_value={
        "verified": False, "title": "", "found_urls": [], "confidence": 0.0, "method": "none",
    })
    def test_verify_no_match(self, mock_mcp):
        mgr = CitationManager()
        citations = [{"keywords": [["quantum computing"]], "raw_tag": "quantum paper"}]
        pool = [{"title": "Deep Learning Survey", "paperId": "p1", "authors": []}]

        verified = mgr.verify(citations, reference_pool=pool)
        assert len(verified) == 1
        assert verified[0]["verified"] is False

    def test_verify_empty_citations(self):
        mgr = CitationManager()
        verified = mgr.verify([])
        assert verified == []

    @patch("api.paper_search.verify_citation_with_mcp", return_value={
        "verified": False, "title": "", "found_urls": [], "confidence": 0.0, "method": "none",
    })
    def test_verify_empty_pool(self, mock_mcp):
        mgr = CitationManager()
        citations = [{"keywords": [["something"]], "raw_tag": "something"}]
        verified = mgr.verify(citations, reference_pool=[])
        assert verified[0]["verified"] is False


class TestDedup:
    """测试去重逻辑"""

    def test_dedup_unique_papers(self):
        mgr = CitationManager()
        citations = [
            {"verified": True, "matched_paper": {"title": "Paper A"}, "paper_id": "p1"},
            {"verified": True, "matched_paper": {"title": "Paper B"}, "paper_id": "p2"},
        ]
        citation_map = mgr.dedup(citations)
        assert len(citation_map) == 2
        assert citation_map["p1"] == 1
        assert citation_map["p2"] == 2

    def test_dedup_duplicate_papers(self):
        mgr = CitationManager()
        citations = [
            {"verified": True, "matched_paper": {"title": "Same Paper"}, "paper_id": "p1"},
            {"verified": True, "matched_paper": {"title": "Same Paper"}, "paper_id": "p1"},
        ]
        citation_map = mgr.dedup(citations)
        assert len(citation_map) == 1
        assert citation_map["p1"] == 1

    def test_dedup_skips_unverified(self):
        mgr = CitationManager()
        citations = [
            {"verified": True, "matched_paper": {"title": "Good"}, "paper_id": "p1"},
            {"verified": False, "matched_paper": None, "paper_id": None},
        ]
        citation_map = mgr.dedup(citations)
        assert len(citation_map) == 1

    def test_dedup_formats_authors(self):
        mgr = CitationManager()
        citations = [
            {
                "verified": True,
                "matched_paper": {
                    "title": "Test Paper",
                    "authors": [{"name": "Alice"}, {"name": "Bob"}],
                },
                "paper_id": "p1",
            },
        ]
        mgr.dedup(citations)
        assert len(mgr._ref_entries) == 1
        assert "Alice" in mgr._ref_entries[0]["entry"]
        assert "Bob" in mgr._ref_entries[0]["entry"]

    def test_dedup_many_authors_uses_et_al(self):
        mgr = CitationManager()
        citations = [
            {
                "verified": True,
                "matched_paper": {
                    "title": "Test",
                    "authors": [{"name": "A"}, {"name": "B"}, {"name": "C"}, {"name": "D"}],
                },
                "paper_id": "p1",
            },
        ]
        mgr.dedup(citations)
        assert "et al." in mgr._ref_entries[0]["entry"]


class TestResolve:
    """测试引用替换"""

    def test_resolve_replaces_citations(self):
        mgr = CitationManager()
        verified = [
            {"verified": True, "matched_paper": {"title": "Paper A"}, "paper_id": "p1", "raw_tag": "Smith 2023"},
        ]
        mgr._citation_map = {"p1": 1}
        mgr._ref_entries = [{"index": 1, "dedup_key": "p1"}]

        text = "As shown in <citation>Smith 2023</citation>."
        result = mgr.resolve(text, verified)
        assert "[1]" in result
        assert "<citation>" not in result

    def test_resolve_unverified_marked_with_question(self):
        mgr = CitationManager()
        verified = [
            {"verified": False, "raw_tag": "Unknown Ref"},
        ]
        mgr._citation_map = {}

        text = "See <citation>Unknown Ref</citation>."
        result = mgr.resolve(text, verified)
        assert "[?]" in result


class TestFormatBibliography:
    """测试参考文献格式化"""

    def test_format_empty(self):
        mgr = CitationManager()
        bib = mgr.format_bibliography()
        assert "No references" in bib

    def test_format_with_entries(self):
        mgr = CitationManager()
        mgr._ref_entries = [
            {"index": 1, "entry": '[1] Alice, "Paper A," CVPR, 2023.'},
            {"index": 2, "entry": '[2] Bob, "Paper B," NeurIPS, 2022.'},
        ]
        bib = mgr.format_bibliography()
        assert "[1]" in bib
        assert "[2]" in bib
        assert "Alice" in bib


class TestGetStats:
    """测试统计功能"""

    def test_get_stats_empty(self):
        mgr = CitationManager()
        stats = mgr.get_stats()
        assert stats["total_ref_entries"] == 0
        assert stats["unique_papers"] == 0

    def test_get_stats_with_entries(self):
        mgr = CitationManager()
        mgr._ref_entries = [
            {"dedup_key": "p1"},
            {"dedup_key": "p2"},
        ]
        stats = mgr.get_stats()
        assert stats["total_ref_entries"] == 2
        assert stats["unique_papers"] == 2


class TestGetUnverifiedCitations:
    """测试未验证引用获取"""

    def test_get_unverified(self):
        mgr = CitationManager()
        citations = [
            {"verified": True},
            {"verified": False},
            {"verified": False},
        ]
        unverified = mgr.get_unverified_citations(citations)
        assert len(unverified) == 2
