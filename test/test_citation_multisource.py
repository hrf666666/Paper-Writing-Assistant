# -*- coding: utf-8 -*-
"""
多源引用验证单元测试

覆盖：
1. URL-as-paperId 识别与 ArXiv/DOI 提取
2. 百度学术搜索（MCP + HTTP）
3. 统一多源降级链 search_papers() / get_paper_details()
4. verify_citation_with_mcp() 多源降级
5. citation_manager.verify() 多源集成
6. 429 限速退避
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestExtractIdFromUrl(unittest.TestCase):
    """测试 URL 中 ArXiv/DOI 提取"""

    def setUp(self):
        from api.paper_search import _extract_id_from_url
        self.extract = _extract_id_from_url

    def test_arxiv_abs_url(self):
        result = self.extract("https://arxiv.org/abs/2312.10175")
        self.assertEqual(result, "ArXiv:2312.10175")

    def test_arxiv_pdf_url(self):
        result = self.extract("https://arxiv.org/pdf/2312.10175")
        self.assertEqual(result, "ArXiv:2312.10175")

    def test_arxiv_html_url(self):
        result = self.extract("https://arxiv.org/html/2505.01458v1")
        self.assertEqual(result, "ArXiv:2505.01458v1")

    def test_doi_url(self):
        result = self.extract("https://doi.org/10.1109/CVPR46437.2021.00123")
        self.assertEqual(result, "DOI:10.1109/CVPR46437.2021.00123")

    def test_non_academic_url_returns_none(self):
        result = self.extract("https://www.youtube.com/watch?v=FvN7CAwuWFQ")
        self.assertIsNone(result)

    def test_non_url_returns_none(self):
        result = self.extract("some_paper_id_123")
        self.assertIsNone(result)

    def test_neurips_pdf_url_returns_none(self):
        result = self.extract("https://papers.neurips.cc/paper_files/paper/2022/file/abc123-Paper.pdf")
        self.assertIsNone(result)

    def test_scribd_url_returns_none(self):
        result = self.extract("https://www.scribd.com/document/669392670/some-doc")
        self.assertIsNone(result)


class TestRateLimitHandling(unittest.TestCase):
    """测试 429 限速退避"""

    def test_handle_rate_limit_429_sets_backoff(self):
        from api.paper_search import _handle_rate_limit_429, _is_rate_limited, _backoff_until
        import api.paper_search as ps

        # 重置
        ps._backoff_until = 0.0
        ps._rate_limit_interval = 2.0

        # 模拟 429 响应
        mock_resp = MagicMock()
        mock_resp.headers = {"Retry-After": "5"}

        _handle_rate_limit_429(mock_resp)

        self.assertTrue(_is_rate_limited())
        self.assertGreater(ps._backoff_until, 0)

        # 清理
        ps._backoff_until = 0.0
        ps._rate_limit_interval = 2.0

    def test_handle_rate_limit_429_default_backoff(self):
        from api.paper_search import _handle_rate_limit_429
        import api.paper_search as ps
        import time

        ps._backoff_until = 0.0
        ps._rate_limit_interval = 2.0

        # 无 Retry-After header，默认 60s
        mock_resp = MagicMock()
        mock_resp.headers = {}

        _handle_rate_limit_429(mock_resp)

        self.assertGreater(ps._backoff_until, time.time() + 50)

        # 清理
        ps._backoff_until = 0.0
        ps._rate_limit_interval = 2.0

    def test_is_rate_limited_false_when_no_backoff(self):
        from api.paper_search import _is_rate_limited
        import api.paper_search as ps

        ps._backoff_until = 0.0
        self.assertFalse(_is_rate_limited())


class TestSearchPapersBaidu(unittest.TestCase):
    """测试百度学术搜索"""

    @patch("api.paper_search._check_mcp_available", return_value=False)
    @patch("api.paper_search._search_baidu_via_http", return_value=[])
    def test_mcp_unavailable_falls_to_http(self, mock_http, mock_mcp):
        from api.paper_search import search_papers_baidu
        result = search_papers_baidu("depth estimation", limit=3)
        mock_http.assert_called_once()
        self.assertEqual(result, [])

    @patch("api.paper_search._check_mcp_available", return_value=True)
    @patch("api.paper_search._search_baidu_via_mcp", return_value=[
        {"paperId": "baidu:test", "title": "Test Paper", "year": 2024,
         "authors": [], "abstract": "", "venue": "", "citationCount": 0,
         "externalIds": {}, "source": "baidu_scholar"}
    ])
    def test_mcp_returns_results(self, mock_mcp_search, mock_mcp_avail):
        from api.paper_search import search_papers_baidu
        result = search_papers_baidu("depth estimation", limit=3)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source"], "baidu_scholar")

    def test_parse_baidu_mcp_results(self):
        from api.paper_search import _parse_baidu_mcp_results
        import json

        raw = json.dumps([{
            "title": "Monocular Depth Estimation",
            "url": "https://xueshu.baidu.com/paper/123",
            "snippet": "A survey of depth estimation methods, 2023",
        }])
        results = _parse_baidu_mcp_results(raw, "depth estimation")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Monocular Depth Estimation")
        self.assertEqual(results[0]["source"], "baidu_scholar")
        self.assertEqual(results[0]["year"], 2023)


class TestUnifiedSearchFallback(unittest.TestCase):
    """测试统一多源降级链"""

    @patch("api.paper_search.search_papers_semantic", return_value=[])
    @patch("api.paper_search.search_papers_baidu", return_value=[
        {"paperId": "baidu:test", "title": "Baidu Paper", "year": 2024,
         "authors": [], "abstract": "", "venue": "", "citationCount": 0,
         "externalIds": {}, "source": "baidu_scholar"}
    ])
    @patch("api.paper_search._get_cache", return_value=None)
    def test_fallback_to_baidu(self, mock_cache, mock_baidu, mock_s2):
        from api.paper_search import search_papers
        result = search_papers("depth estimation", 3)
        self.assertIn("data", result)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["source"], "baidu_scholar")

    @patch("api.paper_search.search_papers_semantic", return_value=[
        {"paperId": "s2_123", "title": "S2 Paper", "year": 2024,
         "authors": [], "abstract": "", "venue": "", "citationCount": 0,
         "externalIds": {}, "source": "semantic_scholar"}
    ])
    @patch("api.paper_search._get_cache", return_value=None)
    def test_s2_preferred_over_baidu(self, mock_cache, mock_s2):
        from api.paper_search import search_papers
        result = search_papers("depth estimation", 3)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["source"], "semantic_scholar")


class TestGetPaperDetailsUrlHandling(unittest.TestCase):
    """测试 get_paper_details_semantic 的 URL 处理"""

    @patch("api.paper_search.requests.get")
    def test_arxiv_url_converted_to_s2_format(self, mock_get):
        from api.paper_search import get_paper_details_semantic

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "paperId": "abc123", "title": "Test", "year": 2024,
            "authors": [], "abstract": "", "venue": "", "citationCount": 0,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = get_paper_details_semantic("https://arxiv.org/abs/2312.10175")

        # 验证 URL 中包含 ArXiv: 格式
        call_url = mock_get.call_args[0][0]
        self.assertIn("ArXiv:", call_url)
        self.assertNotIn("https://arxiv.org", call_url)

    @patch("api.paper_search._get_paper_details_from_url_via_mcp", return_value={
        "paperId": "https://www.youtube.com/watch?v=test",
        "title": "Video Title", "year": 2024, "authors": [],
        "abstract": "", "venue": "", "citationCount": 0,
        "externalIds": {}, "source": "mcp_web_reader",
    })
    def test_non_academic_url_uses_mcp_reader(self, mock_mcp):
        from api.paper_search import get_paper_details_semantic

        result = get_paper_details_semantic("https://www.youtube.com/watch?v=test")
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Video Title")
        mock_mcp.assert_called_once()


class TestVerifyCitationMultisource(unittest.TestCase):
    """测试 verify_citation_with_mcp 多源降级"""

    @patch("api.paper_search.search_with_zhipu_mcp", return_value=[
        {"url": "https://arxiv.org/abs/2312.10175", "title": "Test", "snippet": ""}
    ])
    def test_mcp_academic_url_verifies(self, mock_mcp):
        from api.paper_search import verify_citation_with_mcp
        result = verify_citation_with_mcp("Test Paper Title")
        self.assertTrue(result["verified"])
        self.assertEqual(result["method"], "mcp")

    @patch("api.paper_search.search_with_zhipu_mcp", return_value=[])
    @patch("api.paper_search.search_papers_baidu", return_value=[
        {"paperId": "baidu:test", "title": "Test Paper Title", "year": 2024,
         "authors": [], "abstract": "", "venue": "", "citationCount": 0,
         "externalIds": {}, "url": "https://xueshu.baidu.com/123", "source": "baidu_scholar"}
    ])
    @patch("api.paper_search._is_rate_limited", return_value=False)
    def test_fallback_to_baidu(self, mock_rl, mock_baidu, mock_mcp):
        from api.paper_search import verify_citation_with_mcp
        result = verify_citation_with_mcp("Test Paper Title")
        self.assertTrue(result["verified"])
        self.assertEqual(result["method"], "baidu_scholar")

    @patch("api.paper_search.search_with_zhipu_mcp", return_value=[])
    @patch("api.paper_search.search_papers_baidu", return_value=[])
    @patch("api.paper_search.search_papers_semantic", return_value=[
        {"paperId": "s2_123", "title": "Test Paper Title", "year": 2024,
         "authors": [], "abstract": "", "venue": "", "citationCount": 0,
         "externalIds": {}, "source": "semantic_scholar"}
    ])
    @patch("api.paper_search._is_rate_limited", return_value=False)
    def test_fallback_to_semantic_scholar(self, mock_rl, mock_s2, mock_baidu, mock_mcp):
        from api.paper_search import verify_citation_with_mcp
        result = verify_citation_with_mcp("Test Paper Title")
        self.assertTrue(result["verified"])
        self.assertEqual(result["method"], "semantic_scholar")

    @patch("api.paper_search.search_with_zhipu_mcp", return_value=[])
    @patch("api.paper_search.search_papers_baidu", return_value=[])
    @patch("api.paper_search._is_rate_limited", return_value=True)
    def test_s2_skipped_when_rate_limited(self, mock_rl, mock_baidu, mock_mcp):
        from api.paper_search import verify_citation_with_mcp
        result = verify_citation_with_mcp("Test Paper Title")
        self.assertFalse(result["verified"])


class TestCitationManagerMcpIntegration(unittest.TestCase):
    """测试 CitationManager.verify() 的 MCP 集成"""

    @patch("api.paper_search.verify_citation_with_mcp", return_value={
        "verified": True,
        "title": "Test Paper",
        "found_urls": ["https://arxiv.org/abs/1234.5678"],
        "confidence": 0.9,
        "method": "mcp",
        "matched_paper": {
            "title": "Test Paper", "year": 2024,
            "authors": [{"name": "Author A"}],
            "venue": "CVPR", "paperId": "s2_123",
        },
    })
    def test_verify_uses_mcp(self, mock_verify):
        from agent.citation_manager import CitationManager

        mgr = CitationManager(api_client=MagicMock())
        citations = [{
            "index": 0,
            "raw_tag": "['depth estimation']",
            "keywords": [["depth estimation"]],
        }]

        results = mgr.verify(citations)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["verified"])
        mock_verify.assert_called_once()

    def test_keywords_to_title(self):
        from agent.citation_manager import CitationManager
        mgr = CitationManager()

        title = mgr._keywords_to_title([["deep learning", "neural network"], ["depth estimation"]])
        self.assertIn("deep learning", title)
        self.assertIn("depth estimation", title)

        title_empty = mgr._keywords_to_title([])
        self.assertEqual(title_empty, "")


if __name__ == "__main__":
    unittest.main()
