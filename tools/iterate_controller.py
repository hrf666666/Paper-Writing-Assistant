# -*- coding: utf-8 -*-
"""
Tool: PGEI 迭代控制器 v10.0

架构原则：
- **Python = 裁判**：管线阶段编排、超时控制、通过/失败判定
- **MD = 规则书**：引导 LLM 的规划和评审行为
- **LLM = 运动员**：规划图表、写 TikZ、评审图片、修改代码

管线阶段（硬约束）：
1. PLAN   → LLM 规划图表（或使用预计算的 plan）
2. GEN    → LLM 写 TikZ → Python 编译
3. EVAL   → Vision LLM 评审
4. REVISE → LLM 基于反馈修改 TikZ → Python 编译
5. 重复 3-4 直到通过或达到最大迭代
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3
PASS_THRESHOLD = 7.0
# v10.1: 宽容阈值从 0.8 → 0.7（即 score >= 4.9 时宽容通过）
GRACE_THRESHOLD_RATIO = 0.7


def run_pgei_pipeline(
    output_dir: str,
    paper_content: Dict,
    venue: str = "IEEE TCSVT",
    experiment_data: Optional[Dict] = None,
    plan: Optional[Dict] = None,
    enable_critic: bool = True,
    max_iterations: int = MAX_ITERATIONS,
    text_model_alias: str = "glm_5_1",
    vision_model_alias: str = "glm_4_6v",
    project_path: Optional[str] = None,
    content_brief: Optional[Dict] = None,
) -> Dict:
    """
    Run the full PGEI pipeline (v10).

    Python 职责：阶段编排、文件管理、超时控制
    LLM 职责：规划、写 TikZ、评审、修改
    """
    from tools.figure_planner import plan_figures
    from tools.figure_generator import generate_figure_from_plan
    from tools.figure_critic import evaluate_figure

    figures_dir = os.path.join(output_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)

    result = {"plan": None, "figures": [], "summary": ""}
    start_time = time.time()

    # ═══════════════════════════════════════════════════
    # Phase 1: PLAN（LLM 规划，或使用预计算 plan）
    # ═══════════════════════════════════════════════════
    if plan is None:
        logger.info("=" * 60)
        logger.info("[PGEI] Phase 1: PLAN — LLM 规划图表")
        logger.info("=" * 60)
        plan = plan_figures(paper_content, venue, experiment_data,
                            text_model_alias, content_brief)
    else:
        logger.info("[PGEI] Phase 1: 使用预计算的图表计划")

    result["plan"] = plan
    _save_json(os.path.join(output_dir, "figure_plan.json"), plan)

    # ═══════════════════════════════════════════════════
    # Phase 2-4: GEN → EVAL → REVISE 循环
    # ═══════════════════════════════════════════════════
    figure_plans = plan.get("figures", [])
    total_passed = 0

    for fig_plan in figure_plans:
        fig_id = fig_plan.get("fig_id", "unknown")
        fig_type = fig_plan.get("fig_type", "architecture")

        logger.info("=" * 60)
        logger.info(f"[PGEI] 处理: {fig_id} ({fig_type})")
        logger.info("=" * 60)

        fig_result = {
            "fig_id": fig_id,
            "pdf_path": None,
            "png_path": None,
            "tikz_source": None,
            "iterations": 0,
            "final_score": 0,
            "passed": False,
            "report": None,
        }

        feedback_history = []
        previous_tikz = None

        for iteration in range(max_iterations):
            fig_result["iterations"] = iteration + 1
            phase = "REVISE" if previous_tikz else "GEN"
            logger.info(f"\n--- [{phase}] 迭代 {iteration + 1}/{max_iterations} ---")

            # Phase 2/4: GEN/REVISE
            try:
                gen_result = generate_figure_from_plan(
                    fig_plan, figures_dir, venue,
                    feedback=feedback_history or None,
                    project_path=project_path,
                    text_model_alias=text_model_alias,
                    previous_tikz=previous_tikz,
                )
            except Exception as e:
                logger.error(f"[PGEI] 生成失败: {e}")
                break

            pdf_path = gen_result.get("pdf_path")
            png_path = gen_result.get("png_path")
            tikz_code = gen_result.get("tikz_code")

            if not pdf_path or not os.path.exists(pdf_path):
                logger.error(f"[PGEI] PDF 不存在: {pdf_path}")
                # 如果有编译错误且是首次，记录但不重试
                compile_error = gen_result.get("compile_error", "")
                if compile_error and iteration == 0:
                    logger.error(f"[PGEI] TikZ 编译错误: {compile_error[:200]}")
                break

            fig_result["pdf_path"] = pdf_path
            fig_result["png_path"] = png_path
            if tikz_code:
                fig_result["tikz_source"] = gen_result.get("tikz_source")

            # Phase 3: EVAL（可选）
            if not enable_critic:
                fig_result["passed"] = True
                fig_result["final_score"] = -1
                total_passed += 1
                break

            if not png_path or not os.path.exists(png_path):
                # v10.1: 无 PNG 不再自动通过，标记为未评审
                logger.warning(f"[PGEI] {fig_id} 无 PNG，标记为未评审")
                fig_result["passed"] = False
                fig_result["final_score"] = 0
                fig_result["report"] = {"summary": "No PNG available for evaluation"}
                break

            try:
                report = evaluate_figure(
                    png_path, fig_plan, vision_model_alias,
                    tikz_code=tikz_code,
                )
            except Exception as e:
                logger.error(f"[PGEI] 评审失败: {e}")
                # v10.1: 评审失败不再自动通过
                fig_result["passed"] = False
                fig_result["final_score"] = 0
                fig_result["report"] = {"summary": f"Evaluation failed: {e}"}
                break

            fig_result["report"] = report
            score = report.get("overall", 0)
            passed = report.get("passed", False)
            fig_result["final_score"] = score

            logger.info(
                f"[PGEI] 评审: score={score:.1f}, passed={passed}, "
                f"issues={len(report.get('issues', []))}"
            )

            # 判定通过
            if passed:
                logger.info(f"[PGEI] ✓ {fig_id} 通过 (score={score:.1f})")
                fig_result["passed"] = True
                total_passed += 1
                break

            # Phase 4: REVISE — 保存反馈和 TikZ 代码供下次迭代
            if iteration < max_iterations - 1:
                feedback_history.append({
                    "iteration": iteration + 1,
                    "score": score,
                    "issues": report.get("issues", []),
                    "summary": report.get("summary", ""),
                })
                previous_tikz = tikz_code
                logger.info(f"  [→] 进入 REVISE 阶段")
            else:
                logger.warning(f"[PGEI] ⚠ {fig_id} 达到最大迭代 ({max_iterations})")
                if score >= PASS_THRESHOLD * GRACE_THRESHOLD_RATIO:
                    logger.info(f"[PGEI] {fig_id} 宽容通过 (score={score:.1f} >= {PASS_THRESHOLD * GRACE_THRESHOLD_RATIO:.1f})")
                    fig_result["passed"] = True
                    total_passed += 1

        result["figures"].append(fig_result)

    # ═══════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════
    elapsed = time.time() - start_time
    total = len(figure_plans)
    result["summary"] = (
        f"PGEI v10 完成: {total_passed}/{total} 通过, 耗时 {elapsed:.1f}s"
    )

    logger.info(f"\n{'=' * 60}")
    logger.info(f"[PGEI] {result['summary']}")
    logger.info(f"{'=' * 60}")

    _save_json(os.path.join(output_dir, "pgei_result.json"), result)

    return result


def _save_json(path: str, data: Dict):
    """保存 JSON 结果"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
