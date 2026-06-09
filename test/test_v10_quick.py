#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v10 端到端测试 — LLM 生成 TikZ 架构图
使用 tp_qwen3_6_plus 模型（glm_5_1 在 coding plan 端点返回空）
"""

import sys
import os
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S")

OUTPUT_DIR = "/home/bigboss/code/paper-writing-assistant/output/quick_test"
MODEL_ALIAS = "tp_qwen3_6_plus"  # qwen3.6-plus via ali_token_plan


def main():
    with open(os.path.join(OUTPUT_DIR, "figure_plan.json"), "r") as f:
        plan = json.load(f)

    figures_dir = os.path.join(OUTPUT_DIR, "figures")

    from tools.figure_generator import generate_figure_from_plan

    results = []
    for fig in plan["figures"]:
        fig_id = fig["fig_id"]
        fig_type = fig["fig_type"]
        print(f"\n{'='*60}")
        print(f"  生成: {fig_id} ({fig_type}) — {fig.get('title', '')[:50]}")
        print(f"{'='*60}")

        try:
            result = generate_figure_from_plan(
                fig, figures_dir, "IEEE TCSVT",
                text_model_alias=MODEL_ALIAS,
                project_path="/home/bigboss/code/depth_estimation_unify_theory",
            )

            pdf = result.get("pdf_path", "")
            tikz_src = result.get("tikz_source", "")
            pdf_size = os.path.getsize(pdf) if pdf and os.path.exists(pdf) else 0

            status = "OK" if pdf_size > 1000 else "FAIL"
            print(f"  [{status}] PDF: {pdf} ({pdf_size:,} bytes)")
            if tikz_src:
                with open(tikz_src) as f:
                    lines = f.read().splitlines()
                print(f"  TikZ 源码: {len(lines)} 行")
            if result.get("compile_error"):
                print(f"  编译错误: {result['compile_error'][:200]}")

            results.append({"fig_id": fig_id, "status": status, "pdf_size": pdf_size})

        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback; traceback.print_exc()
            results.append({"fig_id": fig_id, "status": "ERROR", "error": str(e)})

    print(f"\n{'='*60}")
    print(f"  结果汇总")
    print(f"{'='*60}")
    ok = sum(1 for r in results if r["status"] == "OK")
    for r in results:
        marker = "✓" if r["status"] == "OK" else "✗"
        print(f"  {marker} {r['fig_id']}: {r['status']}")
    print(f"\n  {ok}/{len(results)} 成功")


if __name__ == "__main__":
    main()
