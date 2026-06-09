# -*- coding: utf-8 -*-
"""
JournalStyleLearner — 从 ref_pdf 深度学习期刊特有的写作风格 (v10.1)

扩展 exemplar_learner.py 的 6 层阅读协议，增加 4 个新维度：
  L7: Content Pattern — 内容编排模式（每章的子节组织顺序、逻辑推进）
  L8: Argument Rhythm — 论证节奏（哪里放数据/图表/引用，哪里详写/略写）
  L9: Depth Gradient — 深度梯度（每个子节的推导深度）
  L10: Figure Preference — 图片风格偏好（从该期刊论文中学习的图表风格）

核心原则：
- 代码 = 裁判（加载 PDF、调用 LLM、保存结果）
- LLM = 运动员（分析风格、提取模式、聚合画像）
- 输出的 JournalStyleProfile 会填充到 VenueProfile 的软约束字段中
"""

from __future__ import annotations

import json
import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 引导文件路径
_SKILL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "skills", "journal_style")


class JournalStyleLearner:
    """从 ref_pdf 深度学习期刊特有的写作风格"""

    def __init__(self, api_client):
        """
        Args:
            api_client: BaseOrchestrator 实例（提供 LLM 调用能力）
        """
        self.api_client = api_client

    def learn(
        self,
        papers: List[Dict],
        venue_name: str,
        existing_profile: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        从参考论文中学习期刊特有的写作风格。

        Args:
            papers: ref_pdf_analyzer 解析的论文列表
                    [{"filename": str, "text": str, "size": int}, ...]
            venue_name: 目标期刊名（用于 prompt 中引导 LLM）
            existing_profile: 已有的 VenueProfile（用于合并）

        Returns:
            JournalStyleProfile dict，包含：
            - content_patterns: 期刊特有的内容编排模式
            - argument_rhythm: 论证节奏
            - depth_gradients: 深度梯度
            - figure_preferences: 图片风格偏好
            - content_emphasis: 内容侧重点
            - reviewer_preferences: 审稿偏好
            - journal_red_flags: 期刊特有的 Red Flags
        """
        if not papers:
            logger.warning("[JournalStyleLearner] 无参考论文，返回空 profile")
            return self._empty_profile()

        logger.info(f"[JournalStyleLearner] 开始学习 {venue_name} 风格，{len(papers)} 篇论文")

        # Step 1: 对每篇论文做扩展分析（L7-L10）
        analyses = []
        for i, paper in enumerate(papers[:5]):  # 最多分析 5 篇
            logger.info(f"[JournalStyleLearner] L7-L10 分析: {paper.get('filename', f'paper_{i}')}")
            analysis = self._analyze_paper_extended(paper, venue_name)
            if analysis:
                analyses.append(analysis)

        if not analyses:
            logger.warning("[JournalStyleLearner] 所有论文分析失败")
            return self._empty_profile()

        # Step 2: 聚合多篇论文的 L7-L10 分析结果
        logger.info("[JournalStyleLearner] 聚合期刊风格画像...")
        profile = self._aggregate_analyses(analyses, venue_name)

        # Step 3: 与已有 VenueProfile 合并
        if existing_profile:
            profile = self._merge_with_existing(profile, existing_profile)

        logger.info(f"[JournalStyleLearner] 学习完成: {venue_name}")
        return profile

    def _analyze_paper_extended(self, paper: Dict, venue_name: str) -> Optional[Dict]:
        """对单篇论文做 L7-L10 扩展分析"""
        text = paper.get("text", "")
        filename = paper.get("filename", "unknown")

        # 截断文本（避免超过 LLM 上下文）
        text_chunk = text[:8000]

        # 加载分析引导
        guide = self._load_guide("journal_analysis_guide.md")

        prompt = f"""Analyze the following paper from {venue_name} to extract journal-specific writing patterns.

## Analysis Guide
{guide}

## Paper Text (excerpt from {filename})
{text_chunk}

## Task
Extract the following dimensions from this paper. Output ONLY valid JSON.

## Output Format
```json
{{
  "content_patterns": {{
    "Introduction": {{
      "opening_style": "problem_motivation | field_history | application_scenario",
      "contribution_format": "bulleted_list | numbered_list | paragraph",
      "contribution_count": <number>,
      "has_paper_structure_paragraph": <true|false>
    }},
    "Related Work": {{
      "organization": "by_approach | by_technique | chronological | by_problem",
      "critique_style": "separate_section | end_of_group | integrated",
      "comparison_depth": "detailed | moderate | brief"
    }},
    "Methodology": {{
      "starts_with": "problem_formulation | overview | motivation | notation",
      "derivation_style": "full | moderate | brief",
      "has_algorithm_box": <true|false>,
      "subsection_count": <number>
    }},
    "Experiments": {{
      "dataset_description": "detailed_table | brief_text | mixed",
      "ablation_style": "table | figure | both",
      "comparison_style": "table | figure | mixed",
      "has_failure_analysis": <true|false>
    }}
  }},
  "argument_rhythm": {{
    "data_placement": "after_each_claim | end_of_subsection | mixed",
    "figure_density": "high | moderate | low",
    "citation_density": "high | moderate | low",
    "paragraph_length": "long(8+sentences) | medium(5-7) | short(3-4)"
  }},
  "depth_gradients": {{
    "Methodology": "full_derivation | key_formulas_only | overview",
    "Experiments": "comprehensive | focused_on_key_results | minimal"
  }},
  "figure_preferences": {{
    "architecture_style": "detailed_boxes | clean_flowchart | mixed",
    "color_scheme": "colorful | muted | grayscale | blue_dominant",
    "annotation_level": "heavy | moderate | minimal",
    "preferred_layout": "horizontal_flow | vertical_flow | grid"
  }},
  "content_emphasis": {{
    "primary_focus": "theory | system_implementation | experimental_validation | mixed",
    "novelty_presentation": "explicit_claims | subtle_integration | comparison_driven"
  }},
  "journal_red_flags": [
    "writing patterns that this journal explicitly avoids"
  ]
}}
```"""

        try:
            response = self.api_client.call_generation(prompt)
            return self._parse_analysis_response(response)
        except Exception as e:
            logger.error(f"[JournalStyleLearner] 分析 {filename} 失败: {e}")
            return None

    def _aggregate_analyses(self, analyses: List[Dict], venue_name: str) -> Dict:
        """聚合多篇论文的分析结果为期刊级风格画像"""
        if len(analyses) == 1:
            return analyses[0]

        # 用 LLM 做聚合（而非代码硬编码投票逻辑）
        # 将所有分析结果交给 LLM 做综合判断
        combined = json.dumps(analyses, ensure_ascii=False, indent=2)

        prompt = f"""You have analyzed {len(analyses)} papers from {venue_name}.
Each paper's analysis is shown below. Please synthesize them into a SINGLE unified journal style profile.

## Individual Paper Analyses
{combined[:12000]}

## Task
Synthesize these into a unified profile. Use the same JSON structure.
For conflicting patterns, choose the MAJORITY pattern.
For depth/rhythm descriptions, use the most common value.
Add journal-specific red_flags if you notice patterns that are consistently absent.

Output ONLY valid JSON (no markdown code blocks)."""

        try:
            response = self.api_client.call_generation(prompt)
            return self._parse_analysis_response(response)
        except Exception as e:
            logger.error(f"[JournalStyleLearner] 聚合失败: {e}")
            # 降级：取第一篇的结果
            return analyses[0]

    def _merge_with_existing(self, learned: Dict, existing: Dict) -> Dict:
        """将学习到的风格与已有的 VenueProfile 合并"""
        # 学习到的风格优先（更具体），但保留已有 profile 中的硬参数
        merged = {**existing, **learned}

        # 对于 dict 类型的字段，做深度合并
        for key in ["content_patterns", "argument_rhythm", "depth_gradients",
                     "figure_preferences", "content_emphasis"]:
            if key in existing and key in learned:
                if isinstance(existing[key], dict) and isinstance(learned[key], dict):
                    merged[key] = {**existing[key], **learned[key]}

        # journal_red_flags 合并去重
        existing_rfs = existing.get("journal_red_flags", [])
        learned_rfs = learned.get("journal_red_flags", [])
        merged["journal_red_flags"] = list(set(existing_rfs + learned_rfs))

        return merged

    def _parse_analysis_response(self, response: str) -> Dict:
        """解析 LLM 的 JSON 输出（复用多层回退策略）"""
        text = response.strip()

        # 去掉 markdown 代码块
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.find("```", start)
            if end == -1:
                end = len(text)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            first_nl = text.find("\n", start)
            if first_nl != -1:
                end = text.find("```", first_nl)
                if end == -1:
                    end = len(text)
                text = text[first_nl + 1:end].strip()
            else:
                text = text[start:].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 平衡括号匹配
            start = text.find("{")
            if start != -1:
                depth = 0
                in_str = False
                esc = False
                for i in range(start, len(text)):
                    c = text[i]
                    if esc:
                        esc = False
                        continue
                    if c == "\\":
                        esc = True
                        continue
                    if c == '"':
                        in_str = not in_str
                        continue
                    if in_str:
                        continue
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(text[start:i + 1])
                            except json.JSONDecodeError:
                                pass
                            break

            logger.warning("[JournalStyleLearner] JSON 解析失败，返回空 profile")
            return self._empty_profile()

    def _empty_profile(self) -> Dict:
        """空 profile（当没有参考论文或分析失败时）"""
        return {
            "content_patterns": {},
            "argument_rhythm": {},
            "depth_gradients": {},
            "figure_preferences": {},
            "content_emphasis": {},
            "reviewer_preferences": [],
            "journal_red_flags": [],
        }

    def _load_guide(self, filename: str) -> str:
        """加载引导文件"""
        path = os.path.join(_SKILL_DIR, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        # 引导文件不存在时返回基本引导
        return (
            "Analyze the paper's writing style patterns:\n"
            "1. How is each section organized? (subsections, logical flow)\n"
            "2. Where are figures/tables/data placed?\n"
            "3. How deep are the derivations?\n"
            "4. What is the figure style?\n"
            "5. What does this journal emphasize?\n"
        )
