# -*- coding: utf-8 -*-
"""
多代理独立审阅 (Multi-Reviewer) — PaperSpine 核心特性

3个独立 Reviewer + Editor Synthesis:
  - Reviewer 1: Methodology Expert — 关注方法设计的合理性
  - Reviewer 2: Experiment Expert — 关注实验的充分性和公平性
  - Reviewer 3: Writing Quality Expert — 关注写作质量和可读性
  - Editor: 综合3个审阅意见，给出最终修改建议

每个 Reviewer 独立审阅，不共享意见，避免从众效应。
"""

from __future__ import annotations

import json
import os
import logging
import re
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


REVIEWERS = [
    {
        "name": "Methodology Expert",
        "focus": "method design rationality, novelty justification, theoretical grounding",
        "checklist": [
            "Is the method design well-motivated?",
            "Are all components necessary and sufficient?",
            "Is the novelty clearly articulated?",
            "Are assumptions stated and justified?",
            "Is the method described with enough detail to reproduce?",
        ],
    },
    {
        "name": "Experiment Expert",
        "focus": "experimental rigor, baseline fairness, metric completeness, ablation coverage",
        "checklist": [
            "Are baselines state-of-the-art and fairly compared?",
            "Are metrics appropriate and comprehensive?",
            "Are ablation studies thorough?",
            "Is the experimental setup clearly described?",
            "Are results statistically significant?",
        ],
    },
    {
        "name": "Writing Quality Expert",
        "focus": "clarity, flow, academic tone, figure/table quality, consistency",
        "checklist": [
            "Is the paper well-structured and easy to follow?",
            "Is the academic tone consistent throughout?",
            "Are figures and tables clear and informative?",
            "Is the terminology consistent?",
            "Are there grammatical or style issues?",
        ],
    },
]


class MultiReviewer:
    """多代理独立审阅协调器"""

    def __init__(self, api_client):
        self.api_client = api_client

    def run(self, chapters: Dict, abstract: str,
            venue_adapter=None, output_dir: str = None) -> Dict[str, Any]:
        """
        执行多代理审阅

        Returns:
            {
                "reviews": List[dict],     # 每个reviewer的审阅
                "editor_synthesis": dict,  # editor综合意见
                "overall_score": float,
                "actionable_items": List[str],
            }
        """
        full_text = abstract + "\n\n" + "\n\n".join(
            str(chapters.get(k, "")) for k in sorted(chapters.keys(), key=lambda x: str(x))
        )

        num_reviewers = 3
        if venue_adapter:
            num_reviewers = venue_adapter.get_num_reviewers()

        # Step 1: 独立审阅
        reviews = []
        for i in range(min(num_reviewers, len(REVIEWERS))):
            reviewer = REVIEWERS[i]
            logger.info(f"  [MultiReviewer] {reviewer['name']} 正在审阅...")
            review = self._conduct_review(reviewer, full_text)
            reviews.append(review)

        # Step 2: Editor 综合
        logger.info("  [MultiReviewer] Editor 综合审阅意见...")
        synthesis = self._editor_synthesis(reviews, full_text)

        # Step 3: 汇总
        scores = [r.get("score", 0) for r in reviews if r.get("score")]
        overall_score = sum(scores) / len(scores) if scores else 0

        actionable = synthesis.get("actionable_items", [])

        result = {
            "reviews": reviews,
            "editor_synthesis": synthesis,
            "overall_score": overall_score,
            "actionable_items": actionable,
        }

        if output_dir:
            result_file = os.path.join(output_dir, "multi_review.json")
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            self._save_report_md(result, output_dir)

        logger.info(f"  [MultiReviewer] 完成: 均分 {overall_score:.1f}, "
              f"{len(actionable)} 个可操作项")
        return result

    def _conduct_review(self, reviewer: Dict, full_text: str) -> Dict:
        """单个 reviewer 独立审阅"""
        prompt = f"""You are **{reviewer['name']}**, an expert reviewer for a top-tier academic venue.

Your focus: {reviewer['focus']}

Review this paper and address each checklist item:

Checklist:
{chr(10).join(f'{i+1}. {item}' for i, item in enumerate(reviewer['checklist']))}

Paper:
{full_text[:5000]}

Output as JSON:
{{
    "reviewer": "{reviewer['name']}",
    "score": <number 0-100>,
    "strengths": ["list of strengths"],
    "weaknesses": ["list of weaknesses"],
    "checklist_responses": [
        {{"item": "checklist question", "passed": true/false, "comment": "brief comment"}}
    ],
    "recommendation": "accept|minor_revision|major_revision|reject",
    "summary": "2-3 sentence review summary"
}}

Only output the JSON object."""

        try:
            response = self.api_client.call_evaluation(prompt)
            if response:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"{reviewer['name']} 审阅失败: {e}")

        return {
            "reviewer": reviewer["name"],
            "score": 50,
            "strengths": [],
            "weaknesses": [],
            "checklist_responses": [],
            "recommendation": "major_revision",
            "summary": "Review failed, defaulting to major revision.",
        }

    def _editor_synthesis(self, reviews: List[Dict], full_text: str) -> Dict:
        """Editor 综合3个审阅意见"""
        reviews_summary = json.dumps(
            [{
                "reviewer": r.get("reviewer", "?"),
                "score": r.get("score", 0),
                "recommendation": r.get("recommendation", "?"),
                "key_weaknesses": r.get("weaknesses", [])[:3],
            } for r in reviews],
            ensure_ascii=False, indent=2
        )

        prompt = f"""You are the **Editor** synthesizing {len(reviews)} independent reviews.

Reviews summary:
{reviews_summary}

Paper (first 3000 chars):
{full_text[:3000]}

Provide:
1. A consensus recommendation
2. Top 5 most actionable improvement items (specific, not vague)
3. Any disagreements between reviewers and how to resolve them

Output as JSON:
{{
    "consensus": "accept|minor_revision|major_revision|reject",
    "overall_assessment": "2-3 sentence summary",
    "actionable_items": ["specific, actionable improvement 1", ...],
    "disagreements": ["disagreement description and resolution"],
    "priority_fixes": ["most critical fixes needed"]
}}

Only output the JSON object."""

        try:
            response = self.api_client.call_evaluation(prompt)
            if response:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"Editor 综合失败: {e}")

        return {
            "consensus": "major_revision",
            "overall_assessment": "Default assessment due to synthesis failure.",
            "actionable_items": ["Improve experimental rigor", "Strengthen novelty claims"],
            "disagreements": [],
            "priority_fixes": ["Review experimental section"],
        }

    def _save_report_md(self, result: Dict, output_dir: str):
        """保存审阅报告"""
        filepath = os.path.join(output_dir, "multi_review_report.md")
        lines = ["# Multi-Reviewer Report\n"]

        for review in result.get("reviews", []):
            lines.append(f"## {review.get('reviewer', 'Unknown')}")
            lines.append(f"**Score**: {review.get('score', 'N/A')}/100")
            lines.append(f"**Recommendation**: {review.get('recommendation', 'N/A')}\n")

            if review.get("strengths"):
                lines.append("**Strengths**:")
                for s in review["strengths"]:
                    lines.append(f"  + {s}")

            if review.get("weaknesses"):
                lines.append("\n**Weaknesses**:")
                for w in review["weaknesses"]:
                    lines.append(f"  - {w}")
            lines.append("")

        synthesis = result.get("editor_synthesis", {})
        lines.append("## Editor Synthesis")
        lines.append(f"**Consensus**: {synthesis.get('consensus', 'N/A')}")
        lines.append(f"**Assessment**: {synthesis.get('overall_assessment', 'N/A')}\n")

        if synthesis.get("actionable_items"):
            lines.append("**Actionable Items**:")
            for item in synthesis["actionable_items"]:
                lines.append(f"  1. {item}")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
