# -*- coding: utf-8 -*-
"""
Tool: 段落级生成控制器

核心思路：
- 每章先规划段落列表（每段有明确目的和要点）
- 逐段生成，注入前文摘要保持连贯
- 每段生成后做轻量检查（有目的？推进论点？与前文衔接？）
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ParagraphController:
    """段落级生成控制器"""

    def __init__(self, api_client=None):
        self.api_client = api_client

    def plan_paragraphs(self, chapter_name: str, outline: Dict,
                         innovation_points: List = None,
                         prev_summary: str = "",
                         anchor_map: Dict = None,
                         section_budget: Dict = None) -> List[Dict]:
        """
        规划段落列表

        Returns:
            [
                {
                    "index": 0,
                    "purpose": "定义研究问题",
                    "key_points": ["非Lambertian场景深度估计是开放问题"],
                    "target_length": 120,
                    "must_include": ["EPI", "Lambertian assumption"],
                    "anchor_to": "innovation_1",
                },
                ...
            ]
        """
        if not self.api_client:
            return []

        target_words = 800
        if section_budget:
            target_words = section_budget.get("target_words", 800)

        innovation_desc = ""
        if innovation_points:
            names = [ip.get("创新点名称", ip.get("name", "")) for ip in innovation_points[:3]]
            innovation_desc = ", ".join(names)

        anchor_desc = ""
        if anchor_map:
            for key, val in anchor_map.items():
                method_sec = val.get("methodology_section", "")
                if chapter_name.lower() in "methodology" and method_sec:
                    anchor_desc += f"- {val.get('name', key)} → {method_sec}\n"

        prompt = f"""You are planning paragraphs for the "{chapter_name}" section of an academic paper.

Target word count: {target_words} words
Innovation points: {innovation_desc or "see project data"}
Previous chapters summary: {prev_summary[:500]}
{anchor_desc}

Plan 5-8 paragraphs. For each paragraph provide:
- purpose: what this paragraph accomplishes (1 sentence)
- key_points: 1-3 key points to cover
- target_length: target word count (sum should ≈ {target_words})
- must_include: 1-3 key terms that must appear
- anchor_to: which innovation point this supports (if any, e.g. "innovation_1")

Output JSON array:
[
    {{
        "index": 0,
        "purpose": "...",
        "key_points": ["point1", "point2"],
        "target_length": 120,
        "must_include": ["term1"],
        "anchor_to": "innovation_1"
    }}
]

```json ... ``` only."""

        try:
            response = self.api_client.call_reasoning(prompt)
            result = self.api_client.parse_json_response(response, default=[])
            if isinstance(result, list) and len(result) > 0:
                return result
        except Exception as e:
            logger.debug(f"[ParaCtrl] 段落规划失败: {e}")

        return []

    def generate_paragraph(self, para_plan: Dict, prev_text: str,
                            chapter_context: str) -> str:
        """生成单个段落"""
        if not self.api_client:
            return ""

        purpose = para_plan.get("purpose", "")
        key_points = para_plan.get("key_points", [])
        target_len = para_plan.get("target_length", 100)
        must_include = para_plan.get("must_include", [])

        prompt = f"""Write ONE academic paragraph for a research paper.

Purpose: {purpose}
Key points to cover: {json.dumps(key_points, ensure_ascii=False)}
Must include terms: {json.dumps(must_include, ensure_ascii=False)}
Target length: ~{target_len} words

Previous paragraph (for continuity):
{prev_text[-500:]}

Chapter context:
{chapter_context[:500]}

Requirements:
- Write in formal academic English
- Smoothly connect to the previous paragraph
- Use precise technical terminology
- Target ~{target_len} words

Output ONLY the paragraph text, no headers or labels:"""

        try:
            return self.api_client.call_generation(prompt)
        except Exception as e:
            logger.warning(f"[ParaCtrl] 段落生成失败: {e}")
            return ""

    def check_paragraph(self, text: str, plan: Dict) -> Dict:
        """
        轻量段落检查（不调 LLM，纯规则）

        Returns:
            {"passed": bool, "issues": [...]}
        """
        issues = []
        target_len = plan.get("target_length", 100)
        must_include = plan.get("must_include", [])

        # 长度检查
        words = len(text.split())
        if words < target_len * 0.5:
            issues.append(f"过短: {words} 词 (目标 {target_len})")
        elif words > target_len * 1.5:
            issues.append(f"过长: {words} 词 (目标 {target_len})")

        # 必须包含的关键词
        for term in must_include:
            if term.lower() not in text.lower():
                issues.append(f"缺少关键词: {term}")

        # 推进论点信号词
        progress_signals = ["however", "furthermore", "to address", "we propose",
                            "in contrast", "specifically", "notably", "consequently"]
        has_progress = any(sig in text.lower() for sig in progress_signals)
        if not has_progress and len(text.split()) > 50:
            issues.append("缺少论点推进信号词")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "word_count": words,
        }


def run_paragraph_controller(api_client=None) -> ParagraphController:
    """段落控制器工厂"""
    return ParagraphController(api_client)
