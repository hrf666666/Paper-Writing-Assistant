# -*- coding: utf-8 -*-
"""
闭卷重写法 (Closed-Book Rewrite) — PaperSpine 核心特性

流程：
  1. 提取事实：从现有章节中提取关键事实列表
  2. 隐藏原文：仅保留事实列表 + 写作蓝图（大纲 + 理由矩阵 + 动机线程）
  3. 蓝图重写：LLM 仅基于事实列表和蓝图重新写作
  4. 对比检测：计算近似相同段比率，要求 < 35%（避免浅层编辑）
"""

from __future__ import annotations

import json
import os
import logging
import re
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class ClosedBookRewriter:
    """闭卷重写模块"""

    SIMILARITY_THRESHOLD = 0.35  # 近似相同段比率上限

    def __init__(self, api_client):
        self.api_client = api_client

    def rewrite_chapter(self, chapter_name: str, chapter_content: str,
                        outline: Dict, motivation_thread: str,
                        rationale_matrix: Dict,
                        style_profile: Dict = None) -> Dict[str, Any]:
        """
        对单个章节执行闭卷重写

        Returns:
            {
                "original": str,
                "rewritten": str,
                "facts_extracted": int,
                "similarity_ratio": float,
                "passed": bool,
            }
        """
        # Step 1: 提取事实
        facts = self._extract_facts(chapter_name, chapter_content)
        logger.info(f"  [ClosedBook] {chapter_name}: 提取 {len(facts)} 个事实")

        if not facts:
            return {
                "original": chapter_content,
                "rewritten": chapter_content,
                "facts_extracted": 0,
                "similarity_ratio": 1.0,
                "passed": False,
                "reason": "No facts extracted",
            }

        # Step 2: 构建蓝图（不含原文）
        blueprint = self._build_blueprint(
            chapter_name, facts, outline, motivation_thread, rationale_matrix,
            style_profile,
        )

        # Step 3: 蓝图重写
        rewritten = self._rewrite_from_blueprint(chapter_name, blueprint)

        if not rewritten:
            return {
                "original": chapter_content,
                "rewritten": chapter_content,
                "facts_extracted": len(facts),
                "similarity_ratio": 1.0,
                "passed": False,
                "reason": "Rewrite failed",
            }

        # Step 4: 对比检测
        similarity = self._compute_similarity(chapter_content, rewritten)
        passed = similarity < self.SIMILARITY_THRESHOLD

        logger.info(f"  [ClosedBook] {chapter_name}: 相似度 {similarity:.2%}, {'通过' if passed else '未通过'}")

        return {
            "original": chapter_content,
            "rewritten": rewritten,
            "facts_extracted": len(facts),
            "similarity_ratio": similarity,
            "passed": passed,
        }

    def _extract_facts(self, chapter_name: str, content: str) -> List[str]:
        """从章节中提取关键事实"""
        prompt = f"""Extract all verifiable facts from this "{chapter_name}" section.
A fact is any specific claim, number, method name, or relationship that must be preserved.

Content:
{content[:4000]}

Output as a JSON array of strings, each being one atomic fact.
Example: ["Our method achieves 95.3% accuracy on Dataset A", "The module uses 3 convolutional layers"]
Only output the JSON array, no other text."""

        try:
            response = self.api_client.call_generation(prompt)
            if response:
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    facts = json.loads(json_match.group())
                    return [f for f in facts if isinstance(f, str) and len(f) > 10]
        except Exception as e:
            logger.warning(f"事实提取失败: {e}")

        # 降级：按句子分割
        sentences = re.split(r'[.!?]\s', content)
        return [s.strip() for s in sentences if len(s.strip()) > 30][:20]

    def _build_blueprint(self, chapter_name: str, facts: List[str],
                          outline: Dict, motivation_thread: str,
                          rationale_matrix: Dict,
                          style_profile: Dict) -> str:
        """构建写作蓝图（不含原文，只有事实 + 规划）"""
        matrix_rows = rationale_matrix.get("rows", [])
        relevant_rows = [
            r for r in matrix_rows
            if r.get("section", "").lower() in chapter_name.lower()
        ]

        blueprint_parts = [
            f"# Writing Blueprint: {chapter_name}\n",
            f"## Facts to preserve ({len(facts)} total):",
        ]
        for i, fact in enumerate(facts, 1):
            blueprint_parts.append(f"  {i}. {fact}")

        if outline:
            blueprint_parts.append(f"\n## Outline guidance:")
            blueprint_parts.append(json.dumps(outline, ensure_ascii=False)[:1000])

        if motivation_thread:
            blueprint_parts.append(f"\n## Motivation thread:")
            blueprint_parts.append(motivation_thread[:500])

        if relevant_rows:
            blueprint_parts.append(f"\n## Rationale matrix (relevant rows):")
            for row in relevant_rows:
                blueprint_parts.append(
                    f"  - {row.get('design_decision', 'N/A')}: "
                    f"{row.get('motivation', 'N/A')[:80]}"
                )

        if style_profile:
            blueprint_parts.append(f"\n## Style guidance:")
            openings = style_profile.get("preferred_openings", [])
            if openings:
                blueprint_parts.append(f"  Preferred openings: {', '.join(openings[:5])}")
            transitions = style_profile.get("transition_phrases", [])
            if transitions:
                blueprint_parts.append(f"  Transitions: {', '.join(transitions[:5])}")

        return "\n".join(blueprint_parts)

    def _rewrite_from_blueprint(self, chapter_name: str, blueprint: str) -> str:
        """从蓝图重写章节"""
        prompt = f"""You are rewriting the "{chapter_name}" section of an academic paper.

You have ONLY a fact list and writing blueprint — you do NOT have the original text.
Rewrite the section from scratch, incorporating all listed facts naturally.

CRITICAL RULES:
1. Every fact from the list MUST appear in the rewritten text
2. Follow the motivation thread and rationale matrix
3. Maintain the style guidance
4. Do NOT reproduce the original text structure — this is a fresh rewrite
5. Use proper LaTeX-compatible Markdown format

{blueprint}

Write the complete {chapter_name} section now:"""

        try:
            response = self.api_client.call_generation(prompt)
            if response:
                return response.strip()
        except Exception as e:
            logger.warning(f"蓝图重写失败: {e}")
        return ""

    def _compute_similarity(self, original: str, rewritten: str) -> float:
        """计算近似相同段比率（基于 n-gram 重叠）"""
        def _get_sentences(text: str) -> List[str]:
            return [s.strip().lower() for s in re.split(r'[.!?\n]\s*', text)
                    if len(s.strip()) > 20]

        orig_sents = _get_sentences(original)
        rewrite_sents = _get_sentences(rewritten)

        if not orig_sents or not rewrite_sents:
            return 1.0

        similar_count = 0
        for rs in rewrite_sents:
            for os_ in orig_sents:
                # 简单的词级 Jaccard 相似度
                rs_words = set(rs.split())
                os_words = set(os_.split())
                if not rs_words or not os_words:
                    continue
                jaccard = len(rs_words & os_words) / len(rs_words | os_words)
                if jaccard > 0.7:
                    similar_count += 1
                    break

        return similar_count / len(rewrite_sents)
