# -*- coding: utf-8 -*-
"""
Tool: 输出有效性 + 完整度评价 v9.0

三层评价体系（对标 IEEE TCSVT）：
L1: 格式有效性 — .md/.tex/.bib/.pdf 是否生成且合规
L2: 内容完整度 — 结构、引用、公式、图表、数据是否完整
L3: 学术质量 — LLM 驱动的多维度学术质量评价（模拟 TCSVT 审稿）

v9.0 关键改进：
- L1 增加：IEEE格式合规检查（lettersize, markboth, equation环境）
- L2 增加：图表存在性检查（figures/ 目录），LaTeX编译日志分析
- L3 改进：评价 .tex 内容而非截断 .md，评价前先验证 PDF 是否可编译
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class OutputEvaluator:
    """输出有效性 + 完整度评价器 v9.0"""

    # IEEE TCSVT Profile 参数
    TCSVT_PROFILE = {
        "sections": ["Introduction", "Related Work", "Methodology",
                      "Experiments", "Conclusion"],
        "extra_sections": ["Discussion", "Limitations and Future Work"],
        "abstract_words": (200, 300),
        "min_references": 25,
        "min_formulas": 5,
        "min_tables": 3,
        "min_figures": 3,
        "min_ablations": 3,
        "min_sota_methods": 3,
    }

    def __init__(self, output_dir: str, api_client=None):
        self.output_dir = output_dir
        self.api_client = api_client
        self.latex_dir = os.path.join(output_dir, "latex")

    def run_full_evaluation(self, outline: Dict = None,
                             anchor_map: Dict = None,
                             unified_results: Dict = None) -> Dict:
        """执行完整的三层评价"""
        report = {
            "L1_format_validity": self.eval_format_validity(),
            "L2_content_completeness": self.eval_content_completeness(
                outline, anchor_map, unified_results),
            "L3_academic_quality": {},
            "overall": {},
        }

        # L3 需要 api_client
        full_tex = self._read_full_paper_tex()
        if not full_tex:
            full_tex = self._read_full_paper_md()

        if full_tex and self.api_client:
            report["L3_academic_quality"] = self.eval_academic_quality(full_tex)

        l1_score = report["L1_format_validity"].get("score", 0)
        l2_score = report["L2_content_completeness"].get("score", 0)
        l3_score = report["L3_academic_quality"].get("overall_score", 0)

        # 严肃的惩罚机制：如果 L1 关键项未通过，L3 不应给高分
        l1_critical_fails = report["L1_format_validity"].get("critical_fails", [])
        if l1_critical_fails:
            # 每个关键失败扣 L3 分数
            penalty = len(l1_critical_fails) * 10
            l3_score = max(0, l3_score - penalty)
            logger.warning(f"[OutputEval] L1 关键失败 {l1_critical_fails}，L3 扣 {penalty} 分")

        report["overall"] = {
            "L1_score": l1_score,
            "L2_score": l2_score,
            "L3_score": l3_score,
            "L1_passed": report["L1_format_validity"].get("all_passed", False),
            "overall_grade": self._compute_grade(l1_score, l2_score, l3_score),
        }

        report_path = os.path.join(self.output_dir, "evaluation_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self._save_report_md(report)
        logger.info(f"[OutputEval] L1={l1_score} L2={l2_score} L3={l3_score} "
                     f"Grade={report['overall']['overall_grade']}")
        return report

    def eval_format_validity(self) -> Dict:
        """L1 格式有效性检查（v9.0 增强）"""
        checks = {}
        critical_fails = []

        # ── .md 检查 ──
        md_path = os.path.join(self.output_dir, "full_paper.md")
        checks["md_exists"] = os.path.exists(md_path)
        if checks["md_exists"]:
            size = os.path.getsize(md_path)
            checks["md_size_kb"] = round(size / 1024, 1)
            checks["md_min_size"] = size > 15 * 1024

        # ── .tex 检查 ──
        tex_path = os.path.join(self.latex_dir, "main.tex")
        checks["tex_exists"] = os.path.exists(tex_path)
        if checks["tex_exists"]:
            tex_content = open(tex_path, "r", encoding="utf-8").read()

            # IEEE 格式合规
            checks["tex_has_ieeetran"] = "IEEEtran" in tex_content
            checks["tex_has_lettersize"] = "lettersize" in tex_content
            checks["tex_has_abstract"] = "\\begin{abstract}" in tex_content
            checks["tex_has_keywords"] = "\\begin{IEEEkeywords}" in tex_content
            checks["tex_has_markboth"] = "\\markboth" in tex_content

            # 公式环境检查
            eq_count = len(re.findall(r'\\begin\{equation\}', tex_content))
            align_count = len(re.findall(r'\\begin\{align\}', tex_content))
            checks["tex_equation_count"] = eq_count + align_count
            checks["tex_has_display_math"] = (eq_count + align_count) >= 3

            # Markdown 残留检查
            md_residuals = len(re.findall(r'^#{1,4}\s+', tex_content, re.MULTILINE))
            bold_residuals = len(re.findall(r'\*\*[^*]+\*\*', tex_content))
            checks["tex_no_markdown"] = md_residuals == 0 and bold_residuals == 0
            checks["tex_md_residuals"] = md_residuals + bold_residuals

            # 引用检查
            checks["tex_cite_count"] = len(re.findall(r'\\cite\{', tex_content))
            checks["tex_has_citations"] = checks["tex_cite_count"] >= 20

            # 表格检查
            checks["tex_table_count"] = len(re.findall(r'\\begin\{table\}', tex_content))
            checks["tex_has_tables"] = checks["tex_table_count"] >= 2

            # 图片检查
            checks["tex_figure_count"] = len(re.findall(r'\\begin\{figure\}', tex_content))
            checks["tex_has_figures"] = checks["tex_figure_count"] >= 1

            # TABLE_CAPTION 残留检查
            checks["tex_no_placeholder"] = "TABLE_CAPTION" not in tex_content

            # 中文内容检查
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', tex_content))
            checks["tex_no_chinese"] = chinese_chars == 0
            checks["tex_chinese_chars"] = chinese_chars

            if not checks["tex_has_ieeetran"]:
                critical_fails.append("missing_ieeetran")
            if not checks["tex_has_display_math"]:
                critical_fails.append("no_display_math")
            if checks["tex_md_residuals"] > 5:
                critical_fails.append("excessive_markdown_residuals")

        # ── .bib 检查 ──
        bib_path = os.path.join(self.latex_dir, "references.bib")
        checks["bib_exists"] = os.path.exists(bib_path)
        if checks["bib_exists"]:
            bib_content = open(bib_path, "r", encoding="utf-8").read()
            checks["bib_entries"] = bib_content.count("@")
            checks["bib_min_entries"] = checks["bib_entries"] >= 25

        # ── .pdf 检查 ──
        pdf_path = os.path.join(self.output_dir, "full_paper.pdf")
        checks["pdf_exists"] = os.path.exists(pdf_path)
        if checks["pdf_exists"]:
            checks["pdf_size_kb"] = round(os.path.getsize(pdf_path) / 1024, 1)
            # PDF 应该 > 100KB（有实际内容）
            checks["pdf_min_size"] = os.path.getsize(pdf_path) > 100 * 1024

        # ── figures/ 目录检查 ──
        figures_dir = os.path.join(self.output_dir, "figures")
        checks["figures_dir_exists"] = os.path.exists(figures_dir)
        if checks["figures_dir_exists"]:
            fig_files = [f for f in os.listdir(figures_dir)
                         if f.endswith(('.pdf', '.png', '.jpg'))]
            checks["figure_files_count"] = len(fig_files)
            checks["figures_min"] = len(fig_files) >= 2
        else:
            checks["figure_files_count"] = 0
            checks["figures_min"] = False

        # ── 编译日志检查 ──
        log_path = os.path.join(self.latex_dir, "main.log")
        checks["compile_log_exists"] = os.path.exists(log_path)
        if checks["compile_log_exists"]:
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    log_content = f.read()
                error_count = log_content.count("! ")
                checks["compile_errors"] = error_count
                checks["compile_success"] = error_count == 0 and "Output written" in log_content
            except Exception:
                checks["compile_errors"] = -1
                checks["compile_success"] = False

        # ── 评分 ──
        key_items = [
            "md_exists", "tex_exists", "tex_has_ieeetran",
            "tex_has_abstract", "tex_has_keywords",
            "tex_no_markdown", "tex_no_placeholder",
            "tex_has_display_math", "tex_has_tables",
            "bib_exists", "pdf_exists", "pdf_min_size",
            "figures_min",
        ]
        passed = sum(1 for k in key_items if checks.get(k))
        score = int(passed / len(key_items) * 100)

        return {
            "checks": checks, "score": score,
            "all_passed": score >= 85,
            "critical_fails": critical_fails,
        }

    def eval_content_completeness(self, outline: Dict = None,
                                   anchor_map: Dict = None,
                                   unified_results: Dict = None) -> Dict:
        """L2 内容完整度检查（对标 TCSVT）"""
        # 优先读取 .tex 内容（更准确）
        full_content = self._read_full_paper_tex()
        if not full_content:
            full_content = self._read_full_paper_md()
        if not full_content:
            return {"score": 0, "checks": {}}

        checks = {}
        profile = self.TCSVT_PROFILE

        # 章节覆盖
        for section in profile["sections"]:
            checks[f"section_{section.lower().replace(' ', '_')}"] = \
                section.lower() in full_content.lower()

        sections_found = sum(1 for k, v in checks.items()
                             if k.startswith("section_") and v)
        checks["sections_complete"] = sections_found >= len(profile["sections"])

        # 字数统计（基于 .tex 中的文本）
        words = len(full_content.split())
        checks["total_words"] = words
        checks["word_count_ok"] = 3000 <= words <= 15000

        # 引用统计
        cite_count = len(re.findall(r'\\cite\{', full_content))
        ref_matches = set(int(r) for r in re.findall(r'\[(\d+)\]', full_content))
        total_citations = cite_count + len(ref_matches)
        checks["citation_count"] = total_citations
        checks["citations_min"] = total_citations >= profile["min_references"]

        # 公式统计
        eq_count = len(re.findall(r'\\begin\{equation\}', full_content))
        align_count = len(re.findall(r'\\begin\{align\}', full_content))
        checks["formula_count"] = eq_count + align_count
        checks["formulas_min"] = checks["formula_count"] >= profile["min_formulas"]

        # 表格统计
        table_count = len(re.findall(r'\\begin\{table\}', full_content))
        checks["table_count"] = table_count
        checks["tables_min"] = table_count >= profile["min_tables"]

        # 图片统计
        fig_count = len(re.findall(r'\\begin\{figure\}', full_content))
        checks["figure_count"] = fig_count
        checks["figures_min"] = fig_count >= profile["min_figures"]

        # 消融实验提及
        ablation_mentions = len(re.findall(
            r'ablation|Ablation', full_content, re.IGNORECASE))
        checks["ablation_mentions"] = ablation_mentions
        checks["ablations_min"] = ablation_mentions >= profile["min_ablations"]

        # BadPix 检查
        checks["has_badpix"] = bool(re.search(
            r'BadPix|bad pixel', full_content, re.IGNORECASE))

        # 占位符检查
        placeholders = len(re.findall(
            r'\[TODO\]|\[PLACEHOLDER\]|\[DATA-PLACEHOLDER\]|\[\?\]|TABLE_CAPTION',
            full_content))
        checks["placeholders"] = placeholders
        checks["no_placeholders"] = placeholders == 0

        # ── 评分 ──
        key_checks = [
            "sections_complete", "word_count_ok", "citations_min",
            "formulas_min", "tables_min", "no_placeholders",
        ]
        passed = sum(1 for k in key_checks if checks.get(k))
        score = int(passed / len(key_checks) * 100)

        return {"checks": checks, "score": score,
                "sections_found": sections_found,
                "total_words": words, "total_citations": total_citations}

    def eval_academic_quality(self, full_text: str) -> Dict:
        """L3 学术质量评价（模拟 TCSVT 审稿）— v9.0 改进版"""
        if not self.api_client:
            return {"overall_score": 0, "error": "无 api_client"}

        # 使用更多内容（最多 16000 字符），且评价 .tex
        text_for_eval = full_text[:16000]

        prompt = f"""You are a senior reviewer for IEEE TCSVT (Transactions on Circuits and Systems for Video Technology).

You are reviewing a paper's LaTeX source code. Be STRICT and CRITICAL. Do NOT give generous scores if the paper has obvious problems.

Evaluate this paper across 8 dimensions (0-100):

1. Novelty Expression: Complete "problem-insight-solution" chains with clear technical novelty?
2. Narrative Progression: Logical progression with 3+ innovations properly motivated?
3. Methodological Rigor: Mathematical formalization with proper equation environments?
4. Experimental Sufficiency: Multiple datasets, SOTA comparisons, ablations, BadPix metrics?
5. Citation Quality: 50+ refs with precise technical relevance using \\cite{{}}?
6. Writing Style: Formal, precise, IEEE-compliant formatting?
7. Data Consistency: All numerical results consistent across Abstract/Experiments?
8. Format Compliance: IEEEtran class, lettersize option, markboth headers, equation numbering?

IMPORTANT: Score CONSERVATIVELY.
- If equations use \\(...\\) instead of \\begin{{equation}}, score format_compliance ≤ 40
- If no real figures (only TikZ placeholders), score experimental_sufficiency ≤ 50
- If references < 30, score citation_quality ≤ 50
- If Markdown residuals (## or **) exist, score format_compliance ≤ 50
- If Chinese text appears in sections, score writing_style ≤ 40

LaTeX source (truncated to {len(text_for_eval)} chars):
{text_for_eval}

Output JSON:
{{
    "dimensions": {{
        "novelty_expression": <0-100>,
        "narrative_progression": <0-100>,
        "methodological_rigor": <0-100>,
        "experimental_sufficiency": <0-100>,
        "citation_quality": <0-100>,
        "writing_style": <0-100>,
        "data_consistency": <0-100>,
        "format_compliance": <0-100>
    }},
    "overall_score": <average>,
    "strengths": ["s1", "s2", "s3"],
    "weaknesses": ["w1", "w2", "w3"],
    "recommendation": "accept|minor_revision|major_revision|reject",
    "key_gaps_vs_tcsvt": ["gap1", "gap2", "gap3"]
}}

```json ... ``` only."""

        try:
            response = self.api_client.call_evaluation(prompt)
            result = self.api_client.parse_json_response(response, default={})
            if isinstance(result, dict) and "dimensions" in result:
                dims = result["dimensions"]
                if isinstance(dims, dict):
                    scores = [v for v in dims.values()
                              if isinstance(v, (int, float))]
                    if scores and "overall_score" not in result:
                        result["overall_score"] = round(
                            sum(scores) / len(scores), 1)
                return result
        except Exception as e:
            logger.error(f"[OutputEval] L3 评价失败: {e}")
        return {"overall_score": 0, "error": "L3 evaluation failed"}

    def _read_full_paper_md(self) -> Optional[str]:
        path = os.path.join(self.output_dir, "full_paper.md")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def _read_full_paper_tex(self) -> Optional[str]:
        """读取 .tex 文件内容（比 .md 更准确反映实际输出）"""
        path = os.path.join(self.latex_dir, "main.tex")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def _compute_grade(self, l1: int, l2: int, l3: int) -> str:
        if l1 < 60:
            return "D"
        avg = l1 * 0.1 + l2 * 0.35 + l3 * 0.55
        if avg >= 80:
            return "A"
        elif avg >= 65:
            return "B"
        elif avg >= 50:
            return "C"
        return "D"

    def _save_report_md(self, report: Dict):
        path = os.path.join(self.output_dir, "evaluation_report.md")
        lines = ["# 输出有效性 + 完整度评价报告 (v9.0)\n"]
        lines.append("**对标**: IEEE TCSVT\n")

        l1 = report.get("L1_format_validity", {})
        lines.append("## L1: 格式有效性\n")
        lines.append(f"- 总分: {l1.get('score', 0)}/100\n")
        for k, v in l1.get("checks", {}).items():
            lines.append(f"- {k}: {v}")
        cf = l1.get("critical_fails", [])
        if cf:
            lines.append(f"\n**关键失败项**: {cf}\n")

        l2 = report.get("L2_content_completeness", {})
        lines.append("\n## L2: 内容完整度\n")
        lines.append(f"- 总分: {l2.get('score', 0)}/100")
        lines.append(f"- 章节覆盖: {l2.get('sections_found', 0)}/5")
        lines.append(f"- 总词数: {l2.get('total_words', 0)}")
        lines.append(f"- 引用数: {l2.get('total_citations', 0)}\n")

        l3 = report.get("L3_academic_quality", {})
        lines.append("## L3: 学术质量（TCSVT 审稿模拟）\n")
        lines.append(f"- 总分: {l3.get('overall_score', 0)}/100\n")
        rec = l3.get("recommendation", "")
        if rec:
            lines.append(f"**审稿建议**: {rec}\n")
        gaps = l3.get("key_gaps_vs_tcsvt", [])
        if gaps:
            lines.append("**与 TCSVT 标准的关键差距:**\n")
            for g in gaps:
                lines.append(f"- {g}")

        overall = report.get("overall", {})
        lines.append("\n## 总体评价\n")
        lines.append(f"- **评级**: {overall.get('overall_grade', '?')}")
        lines.append(f"- L1={overall.get('L1_score', 0)} L2={overall.get('L2_score', 0)} L3={overall.get('L3_score', 0)}")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


def run_output_evaluator(output_dir: str, api_client=None,
                          outline: Dict = None, anchor_map: Dict = None,
                          unified_results: Dict = None) -> Dict:
    evaluator = OutputEvaluator(output_dir, api_client)
    return evaluator.run_full_evaluation(outline, anchor_map, unified_results)
