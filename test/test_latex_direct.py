#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分章节 LaTeX 直出测试
逐章生成 → 逐章编译验证 → 最终组装
"""
import sys
import os
import json
import re
import time
import shutil
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from tools.latex_direct_generator import (
    generate_chapter_latex, assemble_full_paper, compile_full_paper,
    compile_chapter_snippet, LATEX_PREAMBLE, LATEX_CLOSING,
)
from config.project_config import OUTPUT_DIR, PAPER_TITLE

OUTPUT_BASE = "output/latex_direct"
os.makedirs(OUTPUT_BASE, exist_ok=True)


def load_project_data():
    """加载项目数据"""
    data = {}
    for fname in ["innovation_points.json", "experiment_design.json", "model_architecture.json"]:
        fpath = f"{OUTPUT_DIR}/{fname}"
        if os.path.exists(fpath):
            with open(fpath, "r") as f:
                data[fname.replace(".json", "")] = json.load(f)
            print(f"[OK] 加载 {fname}")
        else:
            print(f"[WARN] {fname} 不存在")
    return data


def test_single_chapter(chapter_num: int, project_data: dict, context: str = ""):
    """测试单个章节的 LaTeX 直出"""
    print(f"\n{'='*60}")
    print(f"  Chapter {chapter_num}: LaTeX Direct Generation")
    print(f"{'='*60}")

    start = time.time()
    latex_code, stats = generate_chapter_latex(chapter_num, project_data, context)
    elapsed = time.time() - start

    # 保存
    ch_dir = f"{OUTPUT_BASE}/chapter{chapter_num}"
    os.makedirs(ch_dir, exist_ok=True)

    tex_path = f"{ch_dir}/chapter{chapter_num}.tex"
    with open(tex_path, "w") as f:
        f.write(latex_code)
    print(f"\n[SAVE] {tex_path} ({len(latex_code)} chars)")

    # 编译测试
    print(f"\n--- 编译测试 Ch{chapter_num} ---")
    full_test_tex = LATEX_PREAMBLE + latex_code + LATEX_CLOSING
    success, errors = compile_chapter_snippet(latex_code)

    if success:
        print(f"  编译: ✅ 0 errors")
    else:
        print(f"  编译: ❌ {len(errors)} errors")
        for e in errors[:5]:
            print(f"    ! {e[:100]}")

    # 统计
    print(f"\n--- 统计 ---")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"  子节生成: {stats['sections_generated']}")
    print(f"  编译通过: {stats['sections_passed']}")
    print(f"  编译失败: {stats['sections_failed']}")

    for d in stats.get("details", []):
        status = "✅" if d["success"] else "❌"
        print(f"    {status} {d['section']} {d['title']} ({d['length']} chars)")

    return latex_code, stats


def main():
    # 解析命令行参数
    test_chapters = []
    for arg in sys.argv[1:]:
        if arg.isdigit() and 1 <= int(arg) <= 5:
            test_chapters.append(int(arg))

    if not test_chapters:
        test_chapters = [1, 2, 3, 4, 5]

    print(f"Paper: {PAPER_TITLE}")
    print(f"Test chapters: {test_chapters}")
    print(f"Output: {OUTPUT_BASE}/")

    project_data = load_project_data()

    # 读取已有 markdown 章节作为 context 参考
    context = ""
    chapter_names = ["introduction", "related_work", "methodology",
                     "experiments", "conclusion"]

    all_chapters_latex = {}
    all_stats = {}

    for ch_num in test_chapters:
        # 用已有 md 内容作为上下文参考
        md_path = f"output/chapter{ch_num}/chapter{ch_num}_{chapter_names[ch_num-1]}.md"
        ch_context = ""
        if os.path.exists(md_path):
            with open(md_path) as f:
                md_content = f.read()
            # 只用前 1500 字符作为上下文
            ch_context = f"[Reference content for context - first 1500 chars]:\n{md_content[:1500]}"

        latex_code, stats = test_single_chapter(ch_num, project_data, ch_context)
        all_chapters_latex[ch_num] = latex_code
        all_stats[ch_num] = stats

        # 间隔避免 API 限频
        if ch_num != test_chapters[-1]:
            print("\n[...] 等待 5s 避免限频...")
            time.sleep(5)

    # ═══ 全章组装测试 ═══
    if len(test_chapters) == 5:
        print(f"\n{'='*60}")
        print(f"  Full Paper Assembly + Compilation")
        print(f"{'='*60}")

        chapter_parts = [all_chapters_latex.get(i, "") for i in range(1, 6)]

        # 读取 TikZ 架构图
        tikz_code = ""
        tikz_path = "output/chapter3/architecture_figure.tex"
        if os.path.exists(tikz_path):
            with open(tikz_path) as f:
                tikz_code = f.read()
            # 修复锚点
            for wrong, correct in {'.bottom': '.south', '.top': '.north',
                                   '.left': '.west', '.right': '.east'}.items():
                tikz_code = tikz_code.replace(wrong, correct)

        # 读取 abstract
        abstract = ""
        abs_path = "output/abstract/abstract.md"
        if os.path.exists(abs_path):
            with open(abs_path) as f:
                abstract_md = f.read()
            # 简单清理：去掉 markdown 残留
            abstract = re.sub(r'^#{1,3}\s*Abstract\s*', '', abstract_md, flags=re.MULTILINE)
            abstract = re.sub(r'\*\*(.+?)\*\*', r'\1', abstract)
            abstract = re.sub(r'\*(.+?)\*', r'\1', abstract)
            abstract = abstract.strip()

        full_paper = assemble_full_paper(chapter_parts, tikz_code, abstract, "")

        # 保存
        full_dir = f"{OUTPUT_BASE}/full"
        os.makedirs(full_dir, exist_ok=True)

        tex_path = f"{full_dir}/main.tex"
        with open(tex_path, "w") as f:
            f.write(full_paper)
        print(f"\n[SAVE] {tex_path} ({len(full_paper)} chars)")

        # 编译
        success, errors, log = compile_full_paper(full_paper, full_dir)

        pages_match = re.search(r"Output written on .+?(\d+) pages", log)
        pages = pages_match.group(1) if pages_match else "?"

        if success:
            print(f"\n编译结果: ✅ 0 errors, {pages} pages")
        else:
            print(f"\n编译结果: ❌ {len(errors)} errors, {pages} pages")
            for e in errors[:8]:
                print(f"  ! {e[:120]}")

        pdf_path = f"{full_dir}/main.pdf"
        if os.path.exists(pdf_path):
            size = os.path.getsize(pdf_path)
            print(f"\nPDF: {pdf_path} ({size//1024}KB)")

    # ═══ 总结 ═══
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    total_passed = sum(s["sections_passed"] for s in all_stats.values())
    total_failed = sum(s["sections_failed"] for s in all_stats.values())
    total_gen = sum(s["sections_generated"] for s in all_stats.values())

    for ch_num in sorted(all_stats.keys()):
        s = all_stats[ch_num]
        print(f"  Ch{ch_num}: {s['sections_passed']}/{s['sections_generated']} sections compiled OK")

    print(f"\n  Total: {total_passed}/{total_gen} sections passed, {total_failed} failed")


if __name__ == "__main__":
    main()
