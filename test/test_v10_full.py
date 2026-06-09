#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v10 完整管线测试 — 从零跑 output/quick_test
LLM 生成 TikZ + 编译 + Vision LLM 评审 + 迭代修改
"""

import sys
import os
import json
import re
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S")

OUTPUT_DIR = "/home/bigboss/code/paper-writing-assistant/output/quick_test"
PROJECT_PATH = "/home/bigboss/code/depth_estimation_unify_theory"
TEXT_MODEL = "tp_qwen3_6_plus"   # qwen3.6-plus 稳定快速
VISION_MODEL = "glm_4_6v"        # 视觉评审


def extract_paper_content(tex_path):
    with open(tex_path, "r", encoding="utf-8") as f:
        content = f.read()
    title = ""
    m = re.search(r"\\title\{(.+?)\}", content, re.DOTALL)
    if m:
        title = re.sub(r"\\textbf\{([^}]+)\}", r"\1", m.group(1))
        title = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", title)
    abstract = ""
    m = re.search(r"\\begin\{abstract\}(.+?)\\end\{abstract\}", content, re.DOTALL)
    if m:
        abstract = m.group(1).strip()
    method_text = ""
    m = re.search(r"\\section\{Methodology\}(.+?)(?:\\section\{|\\end\{document\})", content, re.DOTALL)
    if m:
        method_text = m.group(1).strip()[:3000]
    return {"title": title, "abstract": abstract, "method_text": method_text}


def main():
    print("=" * 70)
    print("  v10 完整管线测试 — output/quick_test")
    print(f"  文本模型: {TEXT_MODEL} | 视觉模型: {VISION_MODEL}")
    print("=" * 70)

    # 1. 论文内容
    paper_content = extract_paper_content(os.path.join(OUTPUT_DIR, "main.tex"))
    print(f"\n[1] 论文: {paper_content['title'][:60]}...")

    # 2. 加载预计算 plan
    with open(os.path.join(OUTPUT_DIR, "figure_plan.json"), "r") as f:
        plan = json.load(f)
    print(f"[2] 图表计划: {len(plan['figures'])} 张")

    # 3. 运行 PGEI v10
    print(f"\n[3] 开始 PGEI v10 管线...")
    t0 = time.time()

    from tools.iterate_controller import run_pgei_pipeline

    result = run_pgei_pipeline(
        output_dir=OUTPUT_DIR,
        paper_content=paper_content,
        venue="IEEE TCSVT",
        plan=plan,
        enable_critic=True,     # 启用 Vision LLM 评审
        max_iterations=2,       # 最多 2 轮迭代（节省时间）
        text_model_alias=TEXT_MODEL,
        vision_model_alias=VISION_MODEL,
        project_path=PROJECT_PATH,
    )

    elapsed = time.time() - t0

    # 4. 输出结果
    print("\n" + "=" * 70)
    print(f"  结果汇总 (耗时 {elapsed:.0f}s)")
    print("=" * 70)

    for fig in result.get("figures", []):
        fid = fig.get("fig_id", "?")
        passed = "PASS" if fig.get("passed") else "FAIL"
        score = fig.get("final_score", 0)
        iters = fig.get("iterations", 0)
        pdf = fig.get("pdf_path", "N/A")
        tikz = "有" if fig.get("tikz_source") else "无"

        print(f"\n  [{passed}] {fid}: score={score:.1f}, iters={iters}, TikZ源码={tikz}")
        if pdf and os.path.exists(pdf):
            print(f"    PDF: {pdf} ({os.path.getsize(pdf):,} bytes)")

        if fig.get("report"):
            r = fig["report"]
            scores = r.get("scores", {})
            parts = []
            for k, v in scores.items():
                parts.append(f"{k.split('_')[-1]}={v}")
            print(f"    评审: {', '.join(parts)} | overall={r.get('overall', 0):.1f}")
            issues = r.get("issues", [])
            for iss in issues[:3]:
                print(f"    - [{iss.get('severity','?')}] {iss.get('description','')[:80]}")

    print(f"\n  {result.get('summary', 'N/A')}")

    # 保存
    out_path = os.path.join(OUTPUT_DIR, "pgei_result_v10.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  结果已保存: {out_path}")


if __name__ == "__main__":
    main()
