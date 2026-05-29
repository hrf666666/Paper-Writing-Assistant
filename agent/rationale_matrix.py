# -*- coding: utf-8 -*-
"""
写作理由矩阵 (Rationale Matrix) — PaperSpine 核心特性

事前规划型矩阵（不是事后总结），每行跨越4个维度：
  1. Motivation — 为什么需要这个设计
  2. SOTA Gap — 相对现有方法的优势
  3. Scenario — 在什么场景下有效
  4. Evidence — 用什么证据支撑

浅矩阵检测：拒绝"改善清晰度"类泛泛行，要求每行必须具体。
"""

from __future__ import annotations

import json
import os
import logging
import re
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class RationaleMatrix:
    """写作理由矩阵生成器"""

    # 浅矩阵检测：泛泛而谈的模式
    VAGUE_PATTERNS = [
        r"improve.*clarity",
        r"better.*performance",
        r"enhance.*quality",
        r"more.*effective",
        r"提高.*效果",
        r"改善.*性能",
    ]

    def __init__(self, api_client):
        self.api_client = api_client

    def run(self, project_data: Dict, ref_data: Dict,
            motivation_thread: str, exemplar_dossier: Dict,
            output_dir: str) -> Dict[str, Any]:
        """
        生成写作理由矩阵

        Returns:
            {
                "rows": List[dict],  # 矩阵行
                "matrix_md": str,     # Markdown 格式矩阵
                "quality": dict,      # 矩阵质量评估
            }
        """
        logger.info("[RationaleMatrix] 生成写作理由矩阵...")

        innovations = project_data.get("innovation_points", [])
        arch = project_data.get("model_architecture", {})
        exp = project_data.get("experiment_design", {})

        prompt = f"""Generate a writing rationale matrix for an academic paper.

This is a PLANNING tool (not a summary). Each row represents a design decision that must be justified in the paper.

Paper title: {project_data.get('title', 'N/A')}
Innovation points: {json.dumps(innovations[:5], ensure_ascii=False)[:1500]}
Architecture: {json.dumps(arch, ensure_ascii=False)[:800]}
Experiment design: {json.dumps(exp, ensure_ascii=False)[:500]}

{f'Motivation thread: {motivation_thread[:500]}' if motivation_thread else ''}

Generate 5-8 rows. Each row MUST have these 4 dimensions filled with SPECIFIC content (no vague statements):

Output as JSON array:
[
  {{
    "design_decision": "what design choice is being justified",
    "motivation": "WHY this design is needed - specific problem it solves",
    "sota_gap": "HOW this improves over prior art - specific baseline comparison",
    "scenario": "WHERE this works best - specific condition or dataset",
    "evidence": "WHAT proof supports this - specific metric or experiment",
    "section": "which paper section this row maps to",
    "priority": "must" | "should" | "nice"
  }}
]

IMPORTANT: Every field must contain specific, concrete content. No vague statements like "improves clarity".
Example of GOOD row: "motivation": "Existing methods fail on non-Lambertian surfaces due to assumption of Lambertian reflectance"
Example of BAD row: "motivation": "Improves the overall quality"

Output ONLY the JSON array."""

        rows = []
        try:
            response = self.api_client.call_generation(prompt)
            if response:
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    rows = json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"矩阵生成失败: {e}")

        # 降级
        if not rows:
            rows = self._fallback_matrix(innovations)

        # 浅矩阵检测
        quality = self._validate_matrix(rows)
        if quality.get("vague_rows"):
            logger.warning(f"[RationaleMatrix] 警告: {len(quality['vague_rows'])} 行过于泛泛，已标记")
            for idx in quality["vague_rows"]:
                rows[idx]["_warning"] = "VAGUE — consider making more specific"

        # 生成 Markdown 矩阵
        matrix_md = self._render_matrix_md(rows)

        # 保存
        result = {
            "rows": rows,
            "matrix_md": matrix_md,
            "quality": quality,
        }
        result_file = os.path.join(output_dir, "rationale_matrix.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        md_file = os.path.join(output_dir, "rationale_matrix.md")
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(matrix_md)

        logger.info(f"[RationaleMatrix] 完成: {len(rows)} 行, 质量 {quality.get('score', 'N/A')}")
        return result

    def _validate_matrix(self, rows: List[Dict]) -> Dict:
        """验证矩阵质量，检测浅矩阵"""
        quality = {
            "total_rows": len(rows),
            "vague_rows": [],
            "empty_cells": 0,
            "score": 100,
        }

        for i, row in enumerate(rows):
            vague_count = 0
            for field in ["motivation", "sota_gap", "scenario", "evidence"]:
                val = row.get(field, "")
                if not val or len(val) < 20:
                    quality["empty_cells"] += 1
                    quality["score"] -= 5
                else:
                    for pattern in self.VAGUE_PATTERNS:
                        if re.search(pattern, val, re.IGNORECASE):
                            vague_count += 1
                            break

            if vague_count >= 2:
                quality["vague_rows"].append(i)
                quality["score"] -= 15

        quality["score"] = max(0, quality["score"])
        quality["passed"] = quality["score"] >= 60
        return quality

    def _fallback_matrix(self, innovations: List[Dict]) -> List[Dict]:
        """降级：基于创新点生成矩阵"""
        rows = []
        for i, inn in enumerate(innovations[:5]):
            name = inn.get("创新点名称", f"Design {i+1}")
            value = inn.get("创新点价值", "")
            rows.append({
                "design_decision": name,
                "motivation": f"Existing methods have limitations in {name.lower()}",
                "sota_gap": f"Improves over prior art by {value[:80] if value else 'novel design'}",
                "scenario": "Evaluated on standard benchmarks",
                "evidence": "Quantitative results in experiments section",
                "section": "Methodology" if i < 3 else "Experiments",
                "priority": "must" if i < 2 else "should",
            })
        return rows if rows else [{
            "design_decision": "Overall method design",
            "motivation": "Addresses limitations of existing approaches",
            "sota_gap": "Achieves state-of-the-art performance",
            "scenario": "Standard evaluation benchmarks",
            "evidence": "Quantitative comparisons",
            "section": "Experiments",
            "priority": "must",
        }]

    def _render_matrix_md(self, rows: List[Dict]) -> str:
        """渲染 Markdown 格式矩阵"""
        lines = ["# Writing Rationale Matrix\n"]
        lines.append("| Design Decision | Motivation | SOTA Gap | Scenario | Evidence | Section | Priority |")
        lines.append("|---|---|---|---|---|---|---|")

        for row in rows:
            dd = row.get("design_decision", "N/A")[:40]
            mot = row.get("motivation", "N/A")[:50]
            gap = row.get("sota_gap", "N/A")[:50]
            scn = row.get("scenario", "N/A")[:40]
            evi = row.get("evidence", "N/A")[:40]
            sec = row.get("section", "N/A")
            pri = row.get("priority", "N/A")
            warn = " ⚠️" if row.get("_warning") else ""
            lines.append(f"| {dd}{warn} | {mot} | {gap} | {scn} | {evi} | {sec} | {pri} |")

        return "\n".join(lines)
