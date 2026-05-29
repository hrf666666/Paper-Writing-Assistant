# -*- coding: utf-8 -*-
"""
测试 agent/quality_gate.py - 质量门控
"""

import pytest
from unittest.mock import MagicMock, patch

from agent.quality_gate import QualityGate, QualityReport


class TestQualityReport:
    """测试 QualityReport 数据类"""

    def test_default_values(self):
        report = QualityReport()
        assert report.passed is False
        assert report.overall_score == 0.0
        assert report.dimensions == {}
        assert report.issues == []
        assert report.suggestions == []
        assert report.should_retry is False
        assert report.retry_strategy == ""

    def test_to_dict(self):
        report = QualityReport()
        report.passed = True
        report.overall_score = 85.0
        report.dimensions = {"academic_rigor": 90}
        d = report.to_dict()
        assert d["passed"] is True
        assert d["overall_score"] == 85.0
        assert d["dimensions"] == {"academic_rigor": 90}


class TestQualityGate:
    """测试 QualityGate"""

    def test_init_with_mock_client(self, mock_api_client):
        gate = QualityGate(api_client=mock_api_client)
        assert gate.api_client is mock_api_client
        assert gate.PASS_THRESHOLD == 70.0
        assert gate.MAX_RETRY_ROUNDS == 3

    def test_evaluate_high_score_passes(self, mock_api_client):
        mock_api_client.call_evaluation.return_value = '''```json
{
    "dimensions": {
        "academic_rigor": 85,
        "logical_coherence": 80,
        "citation_naturalness": 75,
        "content_completeness": 90
    },
    "issues": [],
    "suggestions": ["Good work"],
    "should_retry": false,
    "retry_strategy": "revise"
}
```'''
        mock_api_client.parse_json_response.side_effect = lambda resp, default=None: {
            "dimensions": {"academic_rigor": 85, "logical_coherence": 80,
                           "citation_naturalness": 75, "content_completeness": 90},
            "issues": [],
            "suggestions": ["Good work"],
            "should_retry": False,
            "retry_strategy": "revise",
        }

        gate = QualityGate(api_client=mock_api_client)
        report = gate.evaluate("Introduction", "This is the chapter content.")

        assert report.passed is True
        assert report.overall_score == 82.5
        assert len(report.issues) == 0

    def test_evaluate_low_score_fails(self, mock_api_client):
        mock_api_client.call_evaluation.return_value = "response"
        mock_api_client.parse_json_response.side_effect = lambda resp, default=None: {
            "dimensions": {"academic_rigor": 40, "logical_coherence": 50,
                           "citation_naturalness": 30, "content_completeness": 60},
            "issues": [{"dimension": "academic_rigor", "description": "Too informal"}],
            "suggestions": ["Use more formal language"],
            "should_retry": True,
            "retry_strategy": "revise",
        }

        gate = QualityGate(api_client=mock_api_client)
        report = gate.evaluate("Methodology", "Poor content.")

        assert report.passed is False
        assert report.overall_score == 45.0
        assert report.should_retry is True

    def test_evaluate_exception_handling(self, mock_api_client):
        mock_api_client.call_evaluation.side_effect = Exception("API Error")

        gate = QualityGate(api_client=mock_api_client)
        report = gate.evaluate("Chapter", "content")

        assert report.passed is False
        assert report.overall_score == -1
        assert report.should_retry is True
        assert any("system" in iss.get("dimension", "") for iss in report.issues)

    def test_evaluate_non_dict_response(self, mock_api_client):
        mock_api_client.call_evaluation.return_value = "response"
        mock_api_client.parse_json_response.return_value = "not a dict"

        gate = QualityGate(api_client=mock_api_client)
        report = gate.evaluate("Chapter", "content")

        assert report.passed is False
        assert report.overall_score == 0

    def test_should_retry_below_max_rounds(self, mock_api_client):
        gate = QualityGate(api_client=mock_api_client)
        report = QualityReport()
        report.should_retry = True
        report.passed = False

        assert gate.should_retry(report, 0) is True
        assert gate.should_retry(report, 2) is True

    def test_should_retry_at_max_rounds(self, mock_api_client):
        gate = QualityGate(api_client=mock_api_client)
        report = QualityReport()
        report.should_retry = True
        report.passed = False

        assert gate.should_retry(report, 3) is False

    def test_should_retry_when_passed(self, mock_api_client):
        gate = QualityGate(api_client=mock_api_client)
        report = QualityReport()
        report.should_retry = True
        report.passed = True

        assert gate.should_retry(report, 0) is False

    def test_get_history(self, mock_api_client):
        mock_api_client.call_evaluation.return_value = "r"
        mock_api_client.parse_json_response.return_value = {
            "dimensions": {"academic_rigor": 80},
            "issues": [],
            "suggestions": [],
            "should_retry": False,
            "retry_strategy": "",
        }

        gate = QualityGate(api_client=mock_api_client)
        gate.evaluate("Chapter1", "content1")
        gate.evaluate("Chapter2", "content2")

        history = gate.get_history()
        assert len(history) == 2
        assert history[0]["chapter"] == "Chapter1"
        assert history[1]["chapter"] == "Chapter2"
