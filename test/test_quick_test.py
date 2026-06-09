#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v9.2 快速测试 — 在 output/quick_test 运行完整 PGEI 管线
使用已有的 main.tex + figure_plan.json
"""

import sys
import os
import json
import re
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = "/home/bigboss/code/paper-writing-assistant/output/quick_test"
PROJECT_PATH = "/home/bigboss/code/depth_estimation_unify_theory"


def extract_paper_content(tex_path: str) -> dict:
    """从 LaTeX 提取论文内容（简易版）"""
    with open(tex_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取 title
    title = ""
    m = re.search(r"\\title\{(.+?)\}", content, re.DOTALL)
    if m:
        title = m.group(1).strip()
        title = re.sub(r"\\textbf\{([^}]+)\}", r"\1", title)
        title = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", title)

    # 提取 abstract
    abstract = ""
    m = re.search(r"\\begin\{abstract\}(.+?)\\end\{abstract\}", content, re.DOTALL)
    if m:
        abstract = m.group(1).strip()

    # 提取 method section (Section III)
    method_text = ""
    m = re.search(r"\\section\{Methodology\}(.+?)(?:\\section\{|\\end\{document\})", content, re.DOTALL)
    if m:
        method_text = m.group(1).strip()[:3000]

    return {"title": title, "abstract": abstract, "method_text": method_text}


def main():
    print("=" * 70)
    print("  v9.2 PGEI 管线测试 — output/quick_test")
    print("=" * 70)

    # 1. 加载已有的 figure_plan.json
    plan_path = os.path.join(OUTPUT_DIR, "figure_plan.json")
    if os.path.exists(plan_path):
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
        print(f"[OK] 加载 figure_plan.json ({len(plan.get('figures', []))} figures)")
    else:
        print("[WARN] 无 figure_plan.json，将使用 LLM 规划")
        plan = None

    # 2. 提取论文内容
    tex_path = os.path.join(OUTPUT_DIR, "main.tex")
    paper_content = extract_paper_content(tex_path)
    print(f"[OK] 提取论文内容: title={paper_content['title'][:60]}...")

    # 3. 运行 ContentAnalyzer（规则模式）
    print("\n" + "-" * 70)
    print("  Step 1: ContentAnalyzer — 分析论文叙事结构")
    print("-" * 70)

    from tools.content_analyzer import _rule_based_analysis, brief_to_dict

    brief = _rule_based_analysis(paper_content)
    brief_dict = brief_to_dict(brief)
    print(f"  核心贡献: {brief.core_contribution[:80]}...")
    print(f"  创新点: {len(brief.innovation_points)}")
    print(f"  图表需求: {len(brief.figure_needs)}")
    for fn in brief.figure_needs:
        print(f"    - {fn.suggested_fig_type or 'auto'}: {fn.purpose[:60]}")

    # 4. 运行 ExperimentExplorer
    print("\n" + "-" * 70)
    print("  Step 2: ExperimentExplorer — 探索实验数据")
    print("-" * 70)

    if os.path.isdir(PROJECT_PATH):
        from tools.experiment_explorer import explore_experiments, summary_to_dict

        summary = explore_experiments(PROJECT_PATH)
        exp_data = summary_to_dict(summary)
        print(f"  实验结果: {len(summary.available_results)}")
        print(f"  已有图片: {len(summary.available_images)}")
        if summary.comparison_data:
            print(f"  对比数据: {len(summary.comparison_data.methods)} methods, {len(summary.comparison_data.metrics)} metrics")
        if summary.ablation_data:
            print(f"  消融数据: {len(summary.ablation_data.components)} components")
        print(f"  推荐图表: {len(summary.recommended_figures)}")
    else:
        print(f"  [SKIP] 项目路径不存在: {PROJECT_PATH}")
        exp_data = None

    # 5. 为每张图注入 layout_template（如果没有的话）
    if plan and "figures" in plan:
        from figure.layout_templates import select_template, NodeSpec, EdgeSpec

        for fig in plan["figures"]:
            if "layout_template" not in fig:
                nodes = [NodeSpec(id=m["id"], label=m.get("label", ""), is_innovation=m.get("is_innovation", False))
                         for m in fig.get("modules", [])]
                edges = [EdgeSpec(from_id=c["from"], to_id=c["to"])
                         for c in fig.get("connections", [])]
                template = select_template(nodes, edges, fig.get("layout_direction", ""))
                fig["layout_template"] = template.name
                print(f"  自动选择 layout_template: {fig['fig_id']} -> {template.name}")

    # 6. 运行 PGEI 管线
    print("\n" + "-" * 70)
    print("  Step 3: PGEI 管线 — 生成 + 评审 + 迭代")
    print("-" * 70)

    from tools.iterate_controller import run_pgei_pipeline

    result = run_pgei_pipeline(
        output_dir=OUTPUT_DIR,
        paper_content=paper_content,
        venue="IEEE TCSVT",
        experiment_data=exp_data,
        plan=plan,
        enable_critic=True,
        max_iterations=3,
        text_model_alias="glm_5_1",
        vision_model_alias="glm_4_6v",
        project_path=PROJECT_PATH,
        content_brief=brief_dict,
    )

    # 7. 输出结果
    print("\n" + "=" * 70)
    print("  结果汇总")
    print("=" * 70)

    for fig_result in result.get("figures", []):
        fig_id = fig_result.get("fig_id", "?")
        passed = fig_result.get("passed", False)
        score = fig_result.get("final_score", 0)
        iters = fig_result.get("iterations", 0)
        pdf = fig_result.get("pdf_path", "N/A")
        marker = "PASS" if passed else "FAIL"
        print(f"  [{marker}] {fig_id}: score={score:.1f}, iters={iters}")
        print(f"         pdf={pdf}")

        if fig_result.get("report"):
            report = fig_result["report"]
            stages = report.get("stages", {})
            if stages:
                for sn, sv in stages.items():
                    st = "PASS" if sv.get("passed") else "FIX"
                    print(f"         {sn}: {st} ({sv.get('score', '?')})")

    print(f"\n  {result.get('summary', 'N/A')}")

    # 保存结果
    result_path = os.path.join(OUTPUT_DIR, "pgei_result_v92.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  结果已保存: {result_path}")

    return result


if __name__ == "__main__":
    main()
