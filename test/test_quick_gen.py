#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v9.2 快速测试 — 仅生成图表，不调用 LLM 评审
在 output/quick_test 生成所有 5 张图
"""

import sys
import os
import json
import re
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

OUTPUT_DIR = "/home/bigboss/code/paper-writing-assistant/output/quick_test"
PROJECT_PATH = "/home/bigboss/code/depth_estimation_unify_theory"


def main():
    print("=" * 70)
    print("  v9.2 图表生成测试（无 LLM 评审）— output/quick_test")
    print("=" * 70)

    # 1. 加载 figure_plan.json
    plan_path = os.path.join(OUTPUT_DIR, "figure_plan.json")
    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)
    figures_dir = os.path.join(OUTPUT_DIR, "figures")
    os.makedirs(figures_dir, exist_ok=True)

    print(f"[OK] 加载 {len(plan.get('figures', []))} figures")

    # 2. 为每张图自动选择 layout_template
    from figure.layout_templates import select_template, NodeSpec, EdgeSpec

    for fig in plan["figures"]:
        if "layout_template" not in fig and fig.get("fig_type") in ("teaser", "module_detail", "architecture"):
            nodes = [NodeSpec(id=m["id"], label=m.get("label", ""), is_innovation=m.get("is_innovation", False))
                     for m in fig.get("modules", [])]
            edges = [EdgeSpec(from_id=c["from"], to_id=c["to"])
                     for c in fig.get("connections", [])]
            template = select_template(nodes, edges, fig.get("layout_direction", ""))
            fig["layout_template"] = template.name

    # 3. 探索实验数据
    exp_data = None
    if os.path.isdir(PROJECT_PATH):
        from tools.experiment_explorer import explore_experiments, summary_to_dict
        summary = explore_experiments(PROJECT_PATH)
        exp_data = summary_to_dict(summary)
        print(f"[OK] 实验数据: {len(summary.available_results)} results, {len(summary.available_images)} images")
        if summary.comparison_data:
            print(f"     对比: {summary.comparison_data.methods}")
            print(f"     指标: {summary.comparison_data.metrics}")

    # 4. 逐张生成图表
    from tools.figure_generator import generate_figure_from_plan

    results = []
    for fig in plan["figures"]:
        fig_id = fig.get("fig_id", "?")
        fig_type = fig.get("fig_type", "unknown")
        layout = fig.get("layout_template", "N/A")
        print(f"\n--- 生成 {fig_id} ({fig_type}, layout={layout}) ---")

        try:
            # 注入实验数据到数据图
            if fig_type in ("ablation", "comparison") and not fig.get("data"):
                if exp_data and "ablation_data" in exp_data:
                    fig["data"] = exp_data.get("ablation_data" if fig_type == "ablation" else "comparison_data")

            result = generate_figure_from_plan(
                fig, figures_dir, "IEEE TCSVT",
                project_path=PROJECT_PATH,
            )
            pdf_path = result.get("pdf_path", "N/A")
            png_path = result.get("png_path", "N/A")

            pdf_exists = os.path.exists(pdf_path) if pdf_path else False
            pdf_size = os.path.getsize(pdf_path) if pdf_exists else 0

            status = "OK" if pdf_exists and pdf_size > 1000 else "WARN"
            print(f"  [{status}] PDF: {pdf_path} ({pdf_size:,} bytes)")
            if png_path:
                print(f"         PNG: {png_path}")

            results.append({"fig_id": fig_id, "status": status, "pdf_path": pdf_path, "pdf_size": pdf_size})

        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
            results.append({"fig_id": fig_id, "status": "ERROR", "error": str(e)})

    # 5. 汇总
    print("\n" + "=" * 70)
    print("  生成结果汇总")
    print("=" * 70)
    ok_count = sum(1 for r in results if r["status"] == "OK")
    for r in results:
        print(f"  [{r['status']}] {r['fig_id']}: {r.get('pdf_path', r.get('error', 'N/A'))}")
    print(f"\n  {ok_count}/{len(results)} 成功")


if __name__ == "__main__":
    main()
