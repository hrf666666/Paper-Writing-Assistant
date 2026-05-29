# -*- coding: utf-8 -*-
"""
动机引擎 (Motivation Engine) — PaperSpine 核心特性

强制确认动机后才允许写作，动机线程贯穿全文。

状态机:
  DRAFTING → PENDING_CONFIRM → CONFIRMED → THREAD_BUILT

工作流:
  1. 分析项目数据，生成3个候选动机方向
  2. 用户确认/修改（通过 confirmed_motivation.md 文件交互）
  3. 构建动机线程：映射动机到每个章节的锚点
  4. 持久化动机线程，供所有 skill 读取
"""

from __future__ import annotations

import json
import os
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MotivationAnchor:
    """动机锚点：将动机映射到具体章节"""
    chapter_name: str
    anchor_type: str   # "motivation_hook" | "gap_bridge" | "contribution_claim" | "evidence_support"
    anchor_text: str   # 章节中应包含的关键表述
    priority: str = "must"  # "must" | "should" | "nice"


class MotivationEngine:
    """动机确认与线程管理引擎"""

    def __init__(self, api_client):
        self.api_client = api_client
        self._state = "DRAFTING"

    def run(self, project_data: Dict, ref_data: Dict,
            output_dir: str) -> Dict[str, Any]:
        """
        执行完整的动机确认流程

        Returns:
            {
                "status": "confirmed" | "auto_confirmed",
                "motivation_thread": str,
                "anchors": List[dict],
                "motivation_summary": str,
            }
        """
        # Step 1: 生成候选动机
        logger.info("[MotivationEngine] 生成候选动机方向...")
        candidates = self._generate_motivation_candidates(project_data, ref_data)

        # 保存候选到文件
        motivation_file = os.path.join(output_dir, "motivation_candidates.md")
        self._save_candidates(candidates, motivation_file)
        logger.info(f"[MotivationEngine] 候选动机已保存到 {motivation_file}")

        # Step 2: 检查用户是否已确认
        confirmed_file = os.path.join(output_dir, "confirmed_motivation.md")
        if os.path.exists(confirmed_file):
            with open(confirmed_file, 'r', encoding='utf-8') as f:
                confirmed_motivation = f.read().strip()
            if confirmed_motivation:
                logger.info("[MotivationEngine] 检测到已确认的动机文件")
                self._state = "CONFIRMED"
            else:
                confirmed_motivation = self._auto_select(candidates)
                self._state = "AUTO_CONFIRMED"
        else:
            # 自动选择第一个候选（非交互模式下）
            confirmed_motivation = self._auto_select(candidates)
            self._state = "AUTO_CONFIRMED"
            # 创建确认模板
            self._create_confirm_template(confirmed_motivation, candidates, confirmed_file)

        # Step 3: 构建动机线程
        logger.info("[MotivationEngine] 构建动机线程...")
        thread = self._build_motivation_thread(
            confirmed_motivation, project_data
        )

        # Step 4: 生成章节锚点映射
        logger.info("[MotivationEngine] 生成章节锚点...")
        anchors = self._generate_anchors(
            confirmed_motivation, thread, project_data
        )

        # 保存结果
        result = {
            "status": self._state.lower(),
            "motivation_thread": thread,
            "anchors": [a.__dict__ for a in anchors],
            "motivation_summary": confirmed_motivation[:500],
            "candidates": candidates,
        }

        result_file = os.path.join(output_dir, "motivation_result.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"[MotivationEngine] 动机线程构建完成，{len(anchors)} 个锚点")
        return result

    def _generate_motivation_candidates(self, project_data: Dict,
                                         ref_data: Dict) -> List[Dict]:
        """生成3个候选动机方向"""
        innovations = project_data.get("innovation_points", [])
        arch = project_data.get("model_architecture", {})
        gaps = ref_data.get("research_gaps", [])

        prompt = f"""Analyze this research project and generate exactly 3 distinct motivation directions.
Each direction should describe:
1. What problem exists in current research
2. Why this problem matters
3. How this project addresses it

Project innovations: {json.dumps(innovations[:5], ensure_ascii=False)[:1500]}
Model architecture: {json.dumps(arch, ensure_ascii=False)[:800]}
Known research gaps: {json.dumps(gaps[:3], ensure_ascii=False)[:500]}

Output as JSON array with format:
[
  {{
    "direction": "short name",
    "problem": "what problem exists",
    "significance": "why it matters",
    "approach": "how this project addresses it",
    "key_claim": "one sentence that captures the core motivation"
  }}
]
Only output the JSON array, no other text."""

        try:
            response = self.api_client.call_generation(prompt)
            if response:
                # 提取 JSON
                import re
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"LLM 动机生成失败: {e}")

        # 降级：基于创新点自动生成
        return self._fallback_candidates(innovations)

    def _fallback_candidates(self, innovations: List) -> List[Dict]:
        """降级：基于创新点生成候选"""
        candidates = []
        for i, inn in enumerate(innovations[:3]):
            name = inn.get("创新点名称", f"Innovation {i+1}")
            value = inn.get("创新点价值", "Improves performance")
            candidates.append({
                "direction": f"Direction {i+1}: {name}",
                "problem": f"Current methods lack effective solutions for {name.lower()}",
                "significance": value,
                "approach": f"We propose a novel approach for {name.lower()}",
                "key_claim": f"Our method achieves superior {name.lower()} through innovative design",
            })
        return candidates if candidates else [{
            "direction": "General Improvement",
            "problem": "Existing methods have limitations",
            "significance": "Better performance is needed",
            "approach": "We propose an improved method",
            "key_claim": "Our method outperforms existing approaches",
        }]

    def _auto_select(self, candidates: List[Dict]) -> str:
        """自动选择第一个候选作为动机"""
        if candidates:
            c = candidates[0]
            return (
                f"**Direction**: {c.get('direction', 'N/A')}\n"
                f"**Problem**: {c.get('problem', 'N/A')}\n"
                f"**Significance**: {c.get('significance', 'N/A')}\n"
                f"**Approach**: {c.get('approach', 'N/A')}\n"
                f"**Key Claim**: {c.get('key_claim', 'N/A')}"
            )
        return "Default motivation: improve upon existing methods."

    def _create_confirm_template(self, selected: str, candidates: List[Dict],
                                  filepath: str):
        """创建确认模板文件"""
        content = f"""# Motivation Confirmation

## Auto-selected motivation (modify if needed):

{selected}

## All candidates:
"""
        for i, c in enumerate(candidates, 1):
            content += f"\n### Candidate {i}: {c.get('direction', 'N/A')}\n"
            content += f"- Problem: {c.get('problem', 'N/A')}\n"
            content += f"- Significance: {c.get('significance', 'N/A')}\n"
            content += f"- Approach: {c.get('approach', 'N/A')}\n"
            content += f"- Key Claim: {c.get('key_claim', 'N/A')}\n"

        content += """
---
To confirm: keep the content above as-is or edit it.
To select a different candidate: replace the auto-selected content with another candidate.
To stop the pipeline: delete this file or leave it empty.
"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    def _build_motivation_thread(self, motivation: str,
                                  project_data: Dict) -> str:
        """构建贯穿全文的动机线程"""
        innovations = project_data.get("innovation_points", [])

        prompt = f"""Based on the confirmed motivation below, create a "motivation thread" that will weave through every section of an academic paper.

The thread should specify:
1. A core narrative arc (2-3 sentences)
2. How each section connects to the motivation
3. Key phrases that should appear in each section

Confirmed motivation:
{motivation}

Innovation points: {json.dumps(innovations[:5], ensure_ascii=False)[:1000]}

Output format:
CORE_NARRATIVE: [2-3 sentence narrative arc]
INTRO_HOOK: [how to open the introduction]
GAP_BRIDGE: [how to transition from related work to method]
METHOD_JUSTIFY: [why the method design follows from motivation]
EXPERIMENT_VALIDATE: [how experiments validate the motivation]
CONCLUSION_ECHO: [how to echo the motivation in conclusion]

Be specific and actionable. Each item should be 1-2 sentences."""

        try:
            response = self.api_client.call_generation(prompt)
            if response:
                return response.strip()
        except Exception as e:
            logger.warning(f"动机线程构建失败: {e}")

        # 降级
        return (
            f"CORE_NARRATIVE: {motivation[:200]}\n"
            "INTRO_HOOK: Start with the core problem statement.\n"
            "GAP_BRIDGE: Show how existing methods fail to address this.\n"
            "METHOD_JUSTIFY: Each design choice should trace back to the motivation.\n"
            "EXPERIMENT_VALIDATE: Design experiments that directly test the claims.\n"
            "CONCLUSION_ECHO: Reiterate how the motivation was addressed.\n"
        )

    def _generate_anchors(self, motivation: str, thread: str,
                           project_data: Dict) -> List[MotivationAnchor]:
        """生成章节锚点映射"""
        anchors = []
        sections = [
            ("Introduction", "motivation_hook"),
            ("Introduction", "contribution_claim"),
            ("Related Work", "gap_bridge"),
            ("Methodology", "contribution_claim"),
            ("Experiments", "evidence_support"),
            ("Conclusion", "contribution_claim"),
        ]

        # 从动机线程中提取关键短语
        key_claim = ""
        for line in thread.split("\n"):
            if line.startswith("CORE_NARRATIVE:"):
                key_claim = line.replace("CORE_NARRATIVE:", "").strip()
                break

        if not key_claim:
            key_claim = motivation[:200]

        for chapter, anchor_type in sections:
            anchor_text = self._derive_anchor_text(
                chapter, anchor_type, key_claim, project_data
            )
            anchors.append(MotivationAnchor(
                chapter_name=chapter,
                anchor_type=anchor_type,
                anchor_text=anchor_text,
                priority="must" if anchor_type in ("motivation_hook", "contribution_claim") else "should",
            ))

        return anchors

    def _derive_anchor_text(self, chapter: str, anchor_type: str,
                             key_claim: str, project_data: Dict) -> str:
        """推导锚点文本"""
        templates = {
            ("Introduction", "motivation_hook"):
                f"The introduction must establish: {key_claim[:100]}",
            ("Introduction", "contribution_claim"):
                "Clearly enumerate 3-4 contributions with quantitative evidence where possible",
            ("Related Work", "gap_bridge"):
                f"Transition to method by showing existing approaches do not address: {key_claim[:80]}",
            ("Methodology", "contribution_claim"):
                "Each module should be justified by connecting back to the core motivation",
            ("Experiments", "evidence_support"):
                "Design experiments that directly validate each contribution claim",
            ("Conclusion", "contribution_claim"):
                f"Echo the core narrative: {key_claim[:80]}",
        }
        return templates.get((chapter, anchor_type), "Maintain consistency with core motivation")

    def _save_candidates(self, candidates: List[Dict], filepath: str):
        """保存候选动机到文件"""
        content = "# Motivation Candidates\n\n"
        for i, c in enumerate(candidates, 1):
            content += f"## Candidate {i}: {c.get('direction', 'N/A')}\n"
            content += f"- **Problem**: {c.get('problem', 'N/A')}\n"
            content += f"- **Significance**: {c.get('significance', 'N/A')}\n"
            content += f"- **Approach**: {c.get('approach', 'N/A')}\n"
            content += f"- **Key Claim**: {c.get('key_claim', 'N/A')}\n\n"

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
