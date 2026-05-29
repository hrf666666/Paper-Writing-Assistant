# -*- coding: utf-8 -*-
"""
范例学习引擎 (Exemplar Learner) — PaperSpine 6层阅读协议

从 ref_pdf 中深度学习写作决策，输出：
1. exemplar_dossier.md — 每篇参考论文的6层分析档案
2. style_profile.md — 聚合的写作风格画像

6层阅读协议:
  L1: Argument Architecture — 论证架构（主张层次、证据链）
  L2: Section Rhythm — 章节节奏（篇幅分配、过渡模式）
  L3: Claim Calibration — 声明校准（强弱声明比例、限定词使用）
  L4: Evidence Placement — 证据放置（图/表/数据的引用位置模式）
  L5: Sentence Architecture — 句子架构（开头句模式、复杂度分布）
  L6: Reader Contract — 读者契约（预期管理、承诺与兑现）
"""

from __future__ import annotations

import json
import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ExemplarLearner:
    """6层深度范例学习引擎"""

    def __init__(self, api_client):
        self.api_client = api_client

    def run(self, ref_data: Dict, ref_pdf_path: str,
            output_dir: str) -> Dict[str, Any]:
        """
        执行完整的范例学习流程

        Returns:
            {
                "dossier": dict,      # 6层分析档案
                "style_profile": dict, # 聚合风格画像
            }
        """
        logger.info("[ExemplarLearner] 开始范例学习...")

        # Step 1: 从 ref_data 提取参考论文信息
        papers = self._extract_papers(ref_data, ref_pdf_path)
        if not papers:
            logger.warning("[ExemplarLearner] 无参考论文，跳过")
            return {"dossier": {}, "style_profile": {}}

        logger.info(f"[ExemplarLearner] 发现 {len(papers)} 篇参考论文")

        # Step 2: 对每篇论文进行6层分析
        dossier = {}
        for i, paper in enumerate(papers[:5]):  # 最多分析5篇
            paper_name = paper.get("name", f"paper_{i}")
            logger.info(f"[ExemplarLearner] L1-L6 分析: {paper_name}...")

            analysis = self._analyze_paper(paper)
            if analysis:
                dossier[paper_name] = analysis

        # Step 3: 聚合风格画像
        logger.info("[ExemplarLearner] 聚合风格画像...")
        style_profile = self._aggregate_style_profile(dossier)

        # 保存结果
        dossier_file = os.path.join(output_dir, "exemplar_dossier.json")
        with open(dossier_file, 'w', encoding='utf-8') as f:
            json.dump(dossier, f, ensure_ascii=False, indent=2)

        style_file = os.path.join(output_dir, "style_profile.json")
        with open(style_file, 'w', encoding='utf-8') as f:
            json.dump(style_profile, f, ensure_ascii=False, indent=2)

        # 保存人类可读的 Markdown
        self._save_dossier_md(dossier, output_dir)
        self._save_style_md(style_profile, output_dir)

        logger.info(f"[ExemplarLearner] 完成: {len(dossier)} 篇分析, 风格画像已生成")
        return {"dossier": dossier, "style_profile": style_profile}

    def _extract_papers(self, ref_data: Dict, ref_pdf_path: str) -> List[Dict]:
        """从 ref_data 和 ref_pdf_path 提取参考论文"""
        papers = []

        # 从 ref_data 中获取
        if isinstance(ref_data, dict):
            for key in ["papers", "ref_papers", "analyzed_papers"]:
                if key in ref_data:
                    items = ref_data[key]
                    if isinstance(items, list):
                        papers.extend(items)
                    elif isinstance(items, dict):
                        for name, data in items.items():
                            if isinstance(data, dict):
                                data["name"] = name
                                papers.append(data)

            # 从 style_guide 或其他字段提取
            if "style_guide" in ref_data:
                papers.append({
                    "name": "style_guide_source",
                    "style_guide": ref_data["style_guide"],
                })

        # 从 ref_pdf 目录扫描
        if os.path.isdir(ref_pdf_path):
            for fname in os.listdir(ref_pdf_path):
                if fname.lower().endswith(".pdf"):
                    papers.append({
                        "name": fname.replace(".pdf", ""),
                        "path": os.path.join(ref_pdf_path, fname),
                    })

        return papers

    def _analyze_paper(self, paper: Dict) -> Dict:
        """对单篇论文执行6层分析"""
        paper_content = paper.get("content", paper.get("abstract", ""))
        style_guide = paper.get("style_guide", {})

        if not paper_content and not style_guide:
            return {}

        prompt = f"""Perform a 6-layer deep reading analysis of this academic paper excerpt.

Paper info: {json.dumps({k: v for k, v in paper.items() if k != 'content'}, ensure_ascii=False)[:500]}
Content excerpt: {str(paper_content)[:2000]}
Style guide: {json.dumps(style_guide, ensure_ascii=False)[:500]}

Analyze these 6 layers and output as JSON:

L1_ARGUMENT_ARCHITECTURE: {{
    "main_claims": ["list of main claims"],
    "evidence_chain": "how claims are supported",
    "argument_pattern": "deductive|inductive|comparative|hybrid"
}}

L2_SECTION_RHYTHM: {{
    "section_proportions": {{"section_name": approximate_percentage}},
    "transition_style": "how sections connect",
    "pacing": "fast|balanced|deliberate"
}}

L3_CLAIM_CALIBRATION: {{
    "strong_claims": number,
    "hedged_claims": number,
    "hedging_words": ["list of hedging words used"],
    "calibration_ratio": strong_to_hedged_ratio
}}

L4_EVIDENCE_PLACEMENT: {{
    "figure_reference_pattern": "how figures are referenced",
    "table_placement": "where tables appear relative to claims",
    "data_citation_style": "inline|parenthetical|footnote"
}}

L5_SENTENCE_ARCHITECTURE: {{
    "opening_patterns": ["common sentence starters"],
    "avg_sentence_complexity": "simple|moderate|complex",
    "active_voice_ratio": estimated_percentage
}}

L6_READER_CONTRACT: {{
    "promises_made": ["what the paper promises"],
    "promises_kept": ["what is actually delivered"],
    "expectation_management": "how expectations are set"
}}

Output ONLY the JSON object, no other text."""

        try:
            response = self.api_client.call_generation(prompt)
            if response:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"论文分析失败: {e}")

        return self._fallback_analysis(paper)

    def _fallback_analysis(self, paper: Dict) -> Dict:
        """降级分析（不调用 LLM）"""
        return {
            "L1_ARGUMENT_ARCHITECTURE": {
                "main_claims": [],
                "evidence_chain": "standard empirical validation",
                "argument_pattern": "hybrid",
            },
            "L2_SECTION_RHYTHM": {
                "section_proportions": {},
                "transition_style": "standard academic transitions",
                "pacing": "balanced",
            },
            "L3_CLAIM_CALIBRATION": {
                "strong_claims": 3,
                "hedged_claims": 5,
                "hedging_words": ["may", "could", "suggests"],
                "calibration_ratio": 0.6,
            },
            "L4_EVIDENCE_PLACEMENT": {
                "figure_reference_pattern": "figure referenced before discussion",
                "table_placement": "after claim",
                "data_citation_style": "parenthetical",
            },
            "L5_SENTENCE_ARCHITECTURE": {
                "opening_patterns": ["We propose", "Our method", "Experimental results"],
                "avg_sentence_complexity": "moderate",
                "active_voice_ratio": 60,
            },
            "L6_READER_CONTRACT": {
                "promises_made": [],
                "promises_kept": [],
                "expectation_management": "standard",
            },
        }

    def _aggregate_style_profile(self, dossier: Dict) -> Dict:
        """聚合多篇论文的风格画像"""
        if not dossier:
            return {}

        prompt = f"""Based on the following exemplar analyses, create a unified writing style profile.

Analyses: {json.dumps(dossier, ensure_ascii=False)[:3000]}

Output a JSON object with these fields:
{{
    "preferred_openings": ["top 5 sentence opening patterns"],
    "claim_strength": "conservative|moderate|assertive",
    "transition_phrases": ["top 10 transition phrases"],
    "evidence_style": "quantitative|qualitative|balanced",
    "section_flow": "linear|spiral|problem_solution",
    "key_patterns": ["top writing patterns to emulate"],
    "avoid_patterns": ["patterns to avoid"]
}}

Output ONLY the JSON object."""

        try:
            response = self.api_client.call_generation(prompt)
            if response:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"风格聚合失败: {e}")

        return {
            "preferred_openings": ["We propose", "Our method", "Experimental results show"],
            "claim_strength": "moderate",
            "transition_phrases": ["To address this", "Furthermore", "In contrast"],
            "evidence_style": "balanced",
            "section_flow": "linear",
            "key_patterns": ["clear structure", "strong transitions"],
            "avoid_patterns": ["vague claims", "unsupported assertions"],
        }

    def _save_dossier_md(self, dossier: Dict, output_dir: str):
        """保存人类可读的档案"""
        filepath = os.path.join(output_dir, "exemplar_dossier.md")
        content = "# Exemplar Learning Dossier\n\n"
        for name, analysis in dossier.items():
            content += f"## {name}\n\n"
            for layer, data in analysis.items():
                content += f"### {layer}\n"
                content += f"```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```\n\n"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    def _save_style_md(self, profile: Dict, output_dir: str):
        """保存风格画像"""
        filepath = os.path.join(output_dir, "style_profile.md")
        content = "# Writing Style Profile\n\n"
        content += f"```json\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n```\n"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
