#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v10 核心测试 — LLM 生成 TikZ 架构图
只测试 fig1（teaser），确认 LLM→TikZ→PDF 路径通
"""

import sys
import os
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S")

OUTPUT_DIR = "/home/bigboss/code/paper-writing-assistant/output/quick_test"


def main():
    # 加载 figure_plan
    with open(os.path.join(OUTPUT_DIR, "figure_plan.json"), "r") as f:
        plan = json.load(f)

    fig1 = plan["figures"][0]  # fig1 teaser
    figures_dir = os.path.join(OUTPUT_DIR, "figures")

    print(f"测试图表: {fig1['fig_id']} — {fig1['title']}")
    print(f"模块: {[m['label'] for m in fig1['modules']]}")
    print(f"连接: {len(fig1['connections'])} 条")
    print()

    from tools.figure_generator import generate_figure_from_plan

    result = generate_figure_from_plan(
        fig1, figures_dir, "IEEE TCSVT",
        text_model_alias="glm_5_1",
    )

    print(f"\n结果:")
    print(f"  PDF: {result.get('pdf_path', 'N/A')}")
    print(f"  PNG: {result.get('png_path', 'N/A')}")
    if result.get("tikz_source"):
        print(f"  TikZ源码: {result['tikz_source']}")
        with open(result["tikz_source"], "r") as f:
            code = f.read()
        print(f"  TikZ行数: {len(code.splitlines())}")
    if result.get("compile_error"):
        print(f"  编译错误: {result['compile_error'][:300]}")

    if result.get("pdf_path") and os.path.exists(result["pdf_path"]):
        size = os.path.getsize(result["pdf_path"])
        print(f"  PDF大小: {size:,} bytes")
        print("\n✓ LLM→TikZ→PDF 路径成功!")
    else:
        print("\n✗ 失败")


if __name__ == "__main__":
    main()
