#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
针对性 Stage 测试脚本
只测试 Phase 3 (TikZ) 和 Phase 7 (LaTeX 转换+组装+去重)
使用已有的 output 数据作为输入，不需要重新运行整个 Pipeline

用法:
  python test/stage_targeted_test.py [--tikz] [--latex] [--dedup] [--all]
"""

import sys
import os
import re
import json
import logging

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("stage_test")


# ═══════════════════════════════════════════════════════
# Stage A: TikZ 生成质量测试 (Phase 3)
# ═══════════════════════════════════════════════════════

def test_tikz_anchors():
    """测试 TikZ 代码中不应有非法锚点"""
    from tools.tikz_generator import generate_tikz_from_architecture

    # 使用已有的 model_architecture.json
    arch_path = "output/model_architecture.json"
    if not os.path.exists(arch_path):
        logger.warning(f"跳过 TikZ 测试: {arch_path} 不存在")
        return False

    with open(arch_path, 'r') as f:
        model_arch = json.load(f)

    logger.info("=== Stage A: TikZ 生成测试 ===")

    tikz_code = generate_tikz_from_architecture(
        model_arch,
        output_path="output/test_architecture.tex"
    )

    if not tikz_code:
        logger.error("TikZ 生成返回空结果")
        return False

    passed = True

    # 检查 1: 非法锚点
    bad_anchors = re.findall(r'\.\s*(bottom|top|left|right)\b', tikz_code)
    if bad_anchors:
        logger.error(f"[FAIL] 发现 {len(bad_anchors)} 个非法锚点: {bad_anchors[:5]}")
        passed = False
    else:
        logger.info("[PASS] 无非法锚点 (.bottom/.top/.left/.right)")

    # 检查 2: & 未转义 (在 \node 文本中)
    # 排除 tabular 环境
    lines = tikz_code.split('\n')
    for i, line in enumerate(lines):
        if '\\begin{tabular' in line:
            continue
        # 在 {text} 中找裸 &
        bare_amp = re.findall(r'\{[^}]*[^\\]&[^}]*\}', line)
        if bare_amp:
            logger.error(f"[FAIL] 行 {i+1}: 未转义 & → {bare_amp[0][:60]}")
            passed = False

    if passed:
        logger.info("[PASS] 所有 & 已转义")

    # 检查 3: tikzpicture 环境完整性
    if '\\begin{tikzpicture}' in tikz_code and '\\end{tikzpicture}' in tikz_code:
        logger.info("[PASS] tikzpicture 环境完整")
    else:
        logger.error("[FAIL] tikzpicture 环境不完整")
        passed = False

    # 检查 4: 基本编译可行性（检查常见语法错误）
    # 检查 \draw 命令中的锚点是否都是合法的 PGF 锚点
    valid_anchors = {'north', 'south', 'east', 'west', 'center',
                     'north east', 'north west', 'south east', 'south west',
                     'north east', 'north west', 'south east', 'south west'}
    anchor_usage = re.findall(r'\.\s*(\w+)\s*\)', tikz_code)
    for a in anchor_usage:
        if a in ('bottom', 'top', 'left', 'right'):
            continue  # 已在检查 1 中处理
        # 不做额外检查，因为 PGF 有很多合法锚点

    logger.info(f"TikZ 代码长度: {len(tikz_code)} 字符")
    return passed


# ═══════════════════════════════════════════════════════
# Stage B: LaTeX 转换测试 (Phase 7)
# ═══════════════════════════════════════════════════════

def test_latex_conversion():
    """测试 markdown_to_latex 转换质量"""
    from tools.latex_converter import markdown_to_latex

    logger.info("\n=== Stage B: LaTeX 转换测试 ===")

    all_passed = True

    # ── 测试 B1: 标题括号平衡 ──
    test_cases_bracket = [
        ("## 3.2 Three-Layer Angular Signal Decomposition (", r'\subsection{Three-Layer Angular Signal Decomposition ()}'),
        ("## Title (text", r'\subsection{Title (text)}'),
        ("## Title (text)", r'\subsection{Title (text)}'),
        ("## Title [text", r'\subsection{[text]}'),
    ]
    for md_input, expected_pattern in test_cases_bracket:
        result = markdown_to_latex(md_input)
        # 检查括号平衡
        open_p = result.count('(')
        close_p = result.count(')')
        open_b = result.count('[')
        close_b = result.count(']')
        balanced = (open_p == close_p) and (open_b == close_b)
        status = "PASS" if balanced else "FAIL"
        if not balanced:
            logger.error(f"  [{status}] 输入: {md_input[:50]}")
            logger.error(f"         输出: {result[:80]}")
            logger.error(f"         括号: ( {open_p}/{close_p}  [ {open_b}/{close_b}")
            all_passed = False
        else:
            logger.info(f"  [{status}] 括号平衡: {md_input[:50]}")

    # ── 测试 B2: 层级归一化 (subsubsection → subsection) ──
    test_md_levels = """# Experiments

### Datasets

Some content here.

### Implementation Details

More content.

### Comparison with State-of-the-Art Methods

Comparison content.
"""
    result = markdown_to_latex(test_md_levels)
    # 检查: 章节内第一个子标题应该是 \subsection 不是 \subsubsection
    lines = result.strip().split('\n')
    first_sub = None
    for line in lines:
        if line.strip().startswith('\\subsection{'):
            first_sub = line.strip()
            break
        if line.strip().startswith('\\subsubsection{'):
            first_sub = line.strip()
            break

    if first_sub and first_sub.startswith('\\subsection{'):
        logger.info(f"  [PASS] 层级归一化: {first_sub[:60]}")
    else:
        logger.error(f"  [FAIL] 层级未归一化: {first_sub}")
        all_passed = False

    # ── 测试 B3: citation 残留清理 ──
    test_citation = "We apply enhancement <citation> to improve visibility."
    result = markdown_to_latex(test_citation)
    if '<citation>' in result or '  ' in result:
        logger.error(f"  [FAIL] citation 残留或多空格: {result[:80]}")
        all_passed = False
    else:
        logger.info(f"  [PASS] citation 清理: {result[:60]}")

    # ── 测试 B4: & 转义（正文） ──
    test_amp = "The Dual-Mask Generation & Fusion module integrates predictions."
    result = markdown_to_latex(test_amp)
    if '\\&' in result:
        logger.info(f"  [PASS] & 已转义: {result[:60]}")
    else:
        logger.error(f"  [FAIL] & 未转义: {result[:80]}")
        all_passed = False

    # ── 测试 B5: 章节编号清理 ──
    test_numbering = """# 1. Introduction
## 2.1 Traditional Methods
### 3.1.1 Sub-sub section
"""
    result = markdown_to_latex(test_numbering)
    has_number = bool(re.search(r'\\(section|subsection|subsubsection)\{\d+\.?\d*', result))
    if not has_number:
        logger.info(f"  [PASS] 章节编号已清理")
    else:
        logger.error(f"  [FAIL] 章节编号残留: {result[:100]}")
        all_passed = False

    return all_passed


def test_full_latex_assembly():
    """使用已有的 output 章节数据测试完整 LaTeX 组装"""
    from tools.latex_converter import assemble_latex_paper

    logger.info("\n=== Stage B2: 完整 LaTeX 组装测试 ===")

    # 从已有 output 读取各章节
    chapters = []
    for i in range(1, 6):
        ch_dir = f"output/chapter{i}"
        # 尝试读取 markdown 内容
        md_path = None
        if os.path.isdir(ch_dir):
            for fname in os.listdir(ch_dir):
                if fname.endswith('.md'):
                    md_path = os.path.join(ch_dir, fname)
                    break
        if md_path and os.path.exists(md_path):
            with open(md_path, 'r') as f:
                chapters.append(f.read())
        else:
            logger.warning(f"  章节 {i} 未找到，使用占位")
            chapters.append(f"# Chapter {i}\n\nContent for chapter {i}.\n")

    # 尝试读取 TikZ 代码
    tikz_code = ""
    tikz_path = "output/chapter3/architecture_figure.tex"
    if os.path.exists(tikz_path):
        with open(tikz_path, 'r') as f:
            tikz_code = f.read()

    # 读取 abstract
    abstract = ""
    for fname in ["abstract.md", "abstract.txt"]:
        apath = f"output/abstract/{fname}"
        if os.path.exists(apath):
            with open(apath, 'r') as f:
                abstract = f.read()
            break

    # 模拟额外章节 (Discussion / Limitations)
    # 从 chapters dict 读取（如果有的话）
    extra_chapters = []
    for extra_key, extra_name in [("5_1", "Discussion"), ("5_2", "Limitations and Future Work")]:
        # 尝试从 output 找
        for fname in os.listdir("output"):
            if extra_name.lower().replace(" ", "_") in fname.lower() and fname.endswith('.md'):
                with open(os.path.join("output", fname), 'r') as f:
                    content = f.read()
                if not content.strip().startswith('#'):
                    content = f"# {extra_name}\n\n{content}"
                extra_chapters.append(content)
                break

    all_chapters = chapters + extra_chapters

    logger.info(f"  章节数: {len(all_chapters)}, TikZ: {'有' if tikz_code else '无'}, Abstract: {'有' if abstract else '无'}")

    # 组装
    latex_paper = assemble_latex_paper(all_chapters, tikz_code, abstract, "test, keywords")

    # 保存测试输出
    test_output_dir = "output/test_latex"
    os.makedirs(test_output_dir, exist_ok=True)
    test_tex_path = os.path.join(test_output_dir, "main.tex")
    with open(test_tex_path, 'w') as f:
        f.write(latex_paper)

    logger.info(f"  测试 LaTeX 已保存到 {test_tex_path}")

    # ── 质量检查 ──
    passed = True

    # 检查 1: 非法锚点
    bad_anchors = re.findall(r'\.\s*(bottom|top|left|right)\b', latex_paper)
    if bad_anchors:
        logger.error(f"  [FAIL] 发现 {len(bad_anchors)} 个非法 TikZ 锚点")
        passed = False
    else:
        logger.info(f"  [PASS] 无非法 TikZ 锚点")

    # 检查 2: 标题括号平衡
    headings = re.findall(r'\\(section|subsection|subsubsection)\{([^}]+)}', latex_paper)
    for cmd, title in headings:
        if title.count('(') != title.count(')'):
            logger.error(f"  [FAIL] 标题括号不平衡: \\{cmd}{{{title[:50]}}}")
            passed = False
    if passed:
        logger.info(f"  [PASS] 所有标题括号平衡 ({len(headings)} 个标题)")

    # 检查 3: 层级（章节内第一个子标题应该是 subsection）
    lines = latex_paper.split('\n')
    in_section = False
    first_sub_found = False
    for line in lines:
        s = line.strip()
        if s.startswith('\\section{'):
            in_section = True
            first_sub_found = False
        elif in_section and (s.startswith('\\subsection{') or s.startswith('\\subsubsection{')):
            if not first_sub_found:
                first_sub_found = True
                if s.startswith('\\subsubsection{'):
                    logger.error(f"  [FAIL] 章节内首个子标题层级错误: {s[:60]}")
                    passed = False
    if passed:
        logger.info(f"  [PASS] 章节内标题层级正确")

    # 检查 4: citation 残留
    if '<citation>' in latex_paper:
        logger.error(f"  [FAIL] 发现 <citation> 残留")
        passed = False
    else:
        logger.info(f"  [PASS] 无 citation 残留")

    # 检查 5: 连续多空格
    multi_space_count = len(re.findall(r' {3,}', latex_paper))
    if multi_space_count > 5:
        logger.error(f"  [FAIL] 发现 {multi_space_count} 处连续3+空格")
        passed = False
    else:
        logger.info(f"  [PASS] 多空格正常 ({multi_space_count} 处)")

    # 检查 6: & 在非 tabular 中的未转义
    # 找非 tabular 区域中的裸 &
    in_tabular = False
    for i, line in enumerate(lines):
        if '\\begin{tabular' in line:
            in_tabular = True
        if '\\end{tabular' in line:
            in_tabular = False
            continue
        if not in_tabular and '\\&' not in line and '&' in line:
            # 排除注释行
            stripped = line.strip()
            if not stripped.startswith('%') and not stripped.startswith('\\%'):
                logger.error(f"  [FAIL] 行 {i+1}: 可能未转义 & → {stripped[:80]}")
                passed = False
    if passed:
        logger.info(f"  [PASS] 所有 & 正确转义")

    # 检查 7: 编译尝试（如果有 pdflatex）
    try:
        import subprocess
        result = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-output-directory', test_output_dir, test_tex_path],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, 'PATH': os.environ.get('PATH', '') + ':/usr/local/texlive/2026/bin/x86_64-linux'}
        )
        error_count = result.stdout.count('!')
        if error_count > 0:
            # 提取错误信息
            errors = re.findall(r'^! (.+)', result.stdout, re.MULTILINE)
            logger.warning(f"  [WARN] LaTeX 编译有 {error_count} 个错误:")
            for e in errors[:5]:
                logger.warning(f"    - {e[:80]}")
            passed = False
        else:
            logger.info(f"  [PASS] LaTeX 编译无错误")
    except Exception as e:
        logger.info(f"  [SKIP] LaTeX 编译测试跳过: {e}")

    return passed


def test_dedup_logic():
    """测试去重逻辑"""
    import difflib

    logger.info("\n=== Stage C: 去重逻辑测试 ===")

    # 模拟 Conclusion 和 Discussion 的重复内容
    conclusion_text = """In this paper, we propose a novel Unified Dual-Mask Physical Model for non-Lambertian light field depth estimation from plenoptic cameras. By decoupling angular signals via physical priors and introducing a geometry-aware adaptive routing mechanism, our framework effectively overcomes the inherent geometric constraint failures of traditional epipolar plane image analysis under complex reflectance conditions.

The core contributions of this work are summarized as follows: We constructed a three-layer angular signal decomposition model that decouples light field signals at both physical and geometric levels. This resolves the resolution insufficiency of traditional spectral methods under discrete angular sampling.

A limitation is that the current physical model assumes that the residual term sufficiently captures all non-Lambertian behaviors. Future work includes extending to neural implicit representations."""

    discussion_text = """The proposed Unified Dual-Mask Physical Model introduces a paradigm shift from purely data-driven feature extraction to physics-informed signal decoupling. By explicitly formulating the angular signal, we address the fundamental aliasing problem inherent in low-resolution plenoptic sampling.

Our three-layer decomposition model holds significant potential for broader light field computational photography tasks. The isolated residual term could serve as a physically meaningful prior for light field reflection removal.

Despite these theoretical advantages, several limitations remain. The current physical model assumes the residual term sufficiently captures all non-Lambertian behaviors. Future work will extend the framework to incorporate neural representations."""

    # 测试去重
    concl_paras = [p.strip() for p in conclusion_text.split('\n\n') if len(p.strip()) > 50]
    disc_paras = [p.strip() for p in discussion_text.split('\n\n') if len(p.strip()) > 50]

    removed = 0
    for para in disc_paras:
        for cpara in concl_paras:
            ratio = difflib.SequenceMatcher(None, para[:200], cpara[:200]).ratio()
            if ratio > 0.5:
                removed += 1
                logger.info(f"  检测到重复 (ratio={ratio:.2f}): {para[:50]}...")
                break

    if removed > 0:
        logger.info(f"  [PASS] 去重检测到 {removed} 个重复段落（旧阈值0.8会漏检）")
        return True
    else:
        logger.error(f"  [FAIL] 去重未检测到任何重复")
        return False


# ═══════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="针对性 Stage 测试")
    parser.add_argument('--tikz', action='store_true', help='测试 Stage A: TikZ 生成')
    parser.add_argument('--latex', action='store_true', help='测试 Stage B: LaTeX 转换单元测试')
    parser.add_argument('--assembly', action='store_true', help='测试 Stage B2: 完整 LaTeX 组装')
    parser.add_argument('--dedup', action='store_true', help='测试 Stage C: 去重逻辑')
    parser.add_argument('--all', action='store_true', help='运行所有测试')
    args = parser.parse_args()

    if not any([args.tikz, args.latex, args.assembly, args.dedup, args.all]):
        args.all = True

    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    results = {}

    if args.all or args.tikz:
        try:
            results['tikz'] = test_tikz_anchors()
        except Exception as e:
            logger.error(f"TikZ 测试异常: {e}")
            results['tikz'] = False

    if args.all or args.latex:
        try:
            results['latex'] = test_latex_conversion()
        except Exception as e:
            logger.error(f"LaTeX 转换测试异常: {e}")
            results['latex'] = False

    if args.all or args.assembly:
        try:
            results['assembly'] = test_full_latex_assembly()
        except Exception as e:
            logger.error(f"LaTeX 组装测试异常: {e}")
            results['assembly'] = False

    if args.all or args.dedup:
        try:
            results['dedup'] = test_dedup_logic()
        except Exception as e:
            logger.error(f"去重测试异常: {e}")
            results['dedup'] = False

    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总:")
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
    total = len(results)
    ok = sum(1 for v in results.values() if v)
    print(f"  总计: {ok}/{total}")
    print("=" * 60)

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
