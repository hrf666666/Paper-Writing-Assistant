# -*- coding: utf-8 -*-
"""
Tool: 论文图表生成器 v10.0

架构原则（v10 vs v9.2 的根本改变）：
- **代码 = 裁判**：只做管线编排、编译、文件IO、验证
- **MD = 规则书**：引导 LLM 的设计/评审行为
- **LLM = 运动员**：所有创造性工作（分析、设计、写 TikZ、修改代码）

路由逻辑：
- 架构图 (teaser/module_detail) → LLM 生成 TikZ → Python 编译 pdflatex
- 数据图 (ablation/comparison) → ExperimentExplorer → DataVisualizer → matplotlib（机械性工作，代码做）
- 定性图 (qualitative) → ImageFinder → DataVisualizer grid
"""

import os
import json
import re
import logging
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 引导文件路径
_SKILL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "skills", "figure_tikz_gen")


def generate_figure_from_plan(
    fig_plan: Dict,
    figures_dir: str,
    venue: str = "IEEE TCSVT",
    feedback: Optional[List[Dict]] = None,
    project_path: Optional[str] = None,
    text_model_alias: str = "glm_5_1",
    previous_tikz: Optional[str] = None,
) -> Dict:
    """
    生成图表（v10 架构）。

    Python 职责：路由 + 编译 + 文件管理
    LLM 职责：写 TikZ 代码 / 指导数据图设计
    """
    os.makedirs(figures_dir, exist_ok=True)

    fig_id = fig_plan.get("fig_id", "fig")
    fig_type = fig_plan.get("fig_type", "architecture")
    has_data = bool(fig_plan.get("data"))
    has_images = bool(fig_plan.get("images"))

    # ── 架构图 → LLM 写 TikZ，Python 只编译 ──
    if fig_type in ("teaser", "module_detail", "architecture"):
        return _gen_architecture_llm(
            fig_plan, figures_dir, venue, feedback,
            text_model_alias, previous_tikz,
        )

    # ── 数据图（有数据 → matplotlib 机械性工作；无数据 → LLM TikZ 降级） ──
    if fig_type in ("ablation", "comparison"):
        if has_data:
            return _gen_data_from_provided(fig_plan, figures_dir, venue)
        if project_path:
            result = _gen_data_from_project(fig_plan, figures_dir, venue, project_path)
            if result.get("pdf_path"):
                return result
        # 无数据 → LLM 设计 TikZ 示意版（表格/柱状图的 TikZ 实现）
        logger.info(f"[FigureGen] {fig_id} ({fig_type}) 无数据，LLM TikZ 降级")
        return _gen_data_figure_llm(fig_plan, figures_dir, venue, text_model_alias)

    # ── 定性图（有图片 → matplotlib grid；无图片 → LLM TikZ 降级） ──
    if fig_type == "qualitative":
        if has_images:
            return _gen_qualitative_from_images(fig_plan, figures_dir, venue)
        if project_path:
            result = _gen_qualitative_from_project(fig_plan, figures_dir, venue, project_path)
            if result.get("pdf_path"):
                return result
        # 无图片 → LLM 设计 TikZ 示意版（定性对比示意图）
        logger.info(f"[FigureGen] {fig_id} ({fig_type}) 无图片，LLM TikZ 降级")
        return _gen_data_figure_llm(fig_plan, figures_dir, venue, text_model_alias)

    # ── 未知类型 → LLM 尝试 ──
    logger.info(f"[FigureGen] {fig_id} ({fig_type}) 未知类型，LLM TikZ 降级")
    return _gen_data_figure_llm(fig_plan, figures_dir, venue, text_model_alias)


# ═══════════════════════════════════════════════════════════════
# 架构图：LLM 写 TikZ，Python 只编译
# ═══════════════════════════════════════════════════════════════

def _gen_architecture_llm(
    fig_plan: Dict,
    figures_dir: str,
    venue: str,
    feedback: Optional[List[Dict]],
    text_model_alias: str,
    previous_tikz: Optional[str],
) -> Dict:
    """LLM 生成 TikZ 代码，Python 只负责编译。"""
    fig_id = fig_plan.get("fig_id", "fig")

    # 1. 加载 MD 引导文件
    guide = _load_guide("tikz_design_guide.md")
    examples = _load_guide("tikz_style_examples.md")

    # 2. 构造 prompt
    if previous_tikz and feedback:
        # 迭代模式：LLM 基于反馈修改自己的 TikZ 代码
        prompt = _build_revision_prompt(fig_plan, previous_tikz, feedback, venue, guide)
    else:
        # 首次生成：LLM 从零写 TikZ
        prompt = _build_generation_prompt(fig_plan, venue, guide, examples)

    system_prompt = (
        "You are an expert TikZ developer for top-tier academic paper figures. "
        "You write clean, compilable LaTeX+TikZ code.\n"
        "Output ONLY the complete LaTeX document code, starting from \\documentclass. "
        "Do NOT wrap in markdown code blocks. Do NOT add any explanation outside the code."
    )

    # 3. 调用 LLM
    logger.info(f"[FigureGen] LLM 生成 TikZ: {fig_id}")
    tikz_code = _call_llm(prompt, system_prompt, text_model_alias)

    # 4. 清理 LLM 输出（可能包裹 markdown 代码块）
    tikz_code = _clean_tikz_output(tikz_code)

    # 5. 编译
    result = _compile_tikz(tikz_code, fig_id, figures_dir)

    # 6. 如果编译失败，让 LLM 自动修复（最多 1 次）
    if not result.get("pdf_path") and result.get("compile_error"):
        logger.info(f"[FigureGen] 编译失败，LLM 自动修复: {fig_id}")
        fix_prompt = _build_fix_prompt(tikz_code, result["compile_error"])
        fixed_code = _call_llm(fix_prompt, system_prompt, text_model_alias)
        fixed_code = _clean_tikz_output(fixed_code)

        if fixed_code and "\\documentclass" in fixed_code:
            result = _compile_tikz(fixed_code, fig_id, figures_dir)
            if result.get("pdf_path"):
                tikz_code = fixed_code
                logger.info(f"[FigureGen] 自动修复成功: {fig_id}")
            else:
                logger.warning(f"[FigureGen] 自动修复后仍编译失败: {fig_id}")
        else:
            logger.warning(f"[FigureGen] LLM 修复输出无效: {fig_id}")

    # 7. 保存 TikZ 源码（供后续迭代修改）
    if result.get("pdf_path"):
        tikz_src_path = os.path.join(figures_dir, f"{fig_id}_source.tex")
        with open(tikz_src_path, "w", encoding="utf-8") as f:
            f.write(tikz_code)
        result["tikz_source"] = tikz_src_path
        result["tikz_code"] = tikz_code

    return result


def _build_generation_prompt(fig_plan, venue, guide, examples):
    """首次生成的 prompt"""
    fig_id = fig_plan.get("fig_id", "fig")
    fig_type = fig_plan.get("fig_type", "teaser")
    title = fig_plan.get("title", "")
    caption = fig_plan.get("caption", "")
    size_type = fig_plan.get("size_type", "double")

    # 模块和连接信息
    modules_str = json.dumps(fig_plan.get("modules", []), indent=2, ensure_ascii=False)
    connections_str = json.dumps(fig_plan.get("connections", []), indent=2, ensure_ascii=False)
    groups_str = json.dumps(fig_plan.get("groups", []), indent=2, ensure_ascii=False)
    annotations = fig_plan.get("annotations", [])

    width_hint = "16cm (double-column figure*)" if size_type in ("double", "teaser") else "8cm (single-column figure)"
    height_hint = "4-6cm" if size_type in ("double", "teaser") else "6-8cm"

    prompt = f"""## Task
Generate a complete, compilable LaTeX+TikZ document for the following academic paper figure.

## Design Guide
{guide}

## Style Examples (follow these patterns)
{examples}

## Figure Specification
- **Figure ID**: {fig_id}
- **Type**: {fig_type}
- **Title**: {title}
- **Caption**: {caption}
- **Target Venue**: {venue}
- **Size**: ~{width_hint} wide, ~{height_hint} tall

## Modules (components to draw)
{modules_str}

## Connections (data flow)
{connections_str}

## Groups (visual grouping)
{groups_str}

## Key Annotations
{chr(10).join('- ' + a for a in annotations) if annotations else 'None'}

## Requirements
1. Output a COMPLETE standalone LaTeX document (\\documentclass to \\end{{document}})
2. Follow the design guide color scheme and spacing rules
3. Innovation modules MUST be visually distinct (larger, bolder, different fill)
4. All arrows must be clean paths (no crossing through nodes)
5. All text must be fully visible within node boundaries
6. Use `positioning` library for relative placement (right=of, below=of, etc.)
7. Use `fit` library for group boxes with proper inner sep
8. Total figure must fit the specified size range

## ANTI-OVERLAP RULES (CRITICAL — violation = rejection)
9. **Minimum node spacing**: Every node MUST have `node distance` >= 1.0cm from its neighbors
10. **Z-order layering**: Use `\\pgfonlayer{{background}}` for all arrow/connection paths. Nodes are on the main layer, arrows behind them. Add `\\usepgflayers{{background}}` in preamble.
11. **Label placement**: ALL annotations and edge labels MUST use `midway, above` or `midway, below` positioning — NEVER use absolute coordinates for labels
12. **No absolute coordinates**: Use ONLY relative positioning (`right=2cm of X`, `below=1cm of Y`). NEVER use `at (x,y)` with literal numbers
13. **Text fitting**: Set `text width=Xcm` on nodes with multi-line text to prevent overflow. Use `align=center`
14. **Color coding**: Use soft pastels (fill=blue!10, orange!20, etc.) — NEVER saturated colors (fill=blue, fill=red)
15. **Font hierarchy**: Module names = `\\small\\bfseries`, sub-labels = `\\scriptsize`, annotations = `\\tiny\\itshape`

Generate the TikZ code now:"""

    return prompt


def _build_revision_prompt(fig_plan, previous_tikz, feedback, venue, guide):
    """迭代修改的 prompt"""
    fig_id = fig_plan.get("fig_id", "fig")
    title = fig_plan.get("title", "")

    # 构造反馈摘要
    feedback_str = ""
    for fb in feedback:
        iteration = fb.get("iteration", "?")
        score = fb.get("score", 0)
        issues = fb.get("issues", [])
        summary = fb.get("summary", "")
        feedback_str += f"\n### Iteration {iteration} (score: {score:.1f})\n"
        feedback_str += f"Summary: {summary}\n"
        for issue in issues:
            sev = issue.get("severity", "?")
            dim = issue.get("dimension", "?")
            desc = issue.get("description", "")
            sugg = issue.get("suggestion", "")
            feedback_str += f"- [{sev}] {dim}: {desc}\n  Fix: {sugg}\n"

    prompt = f"""## Task
Revise the following TikZ figure code based on reviewer feedback.

## Design Guide (for reference)
{guide}

## Figure: {title} ({fig_id})
Target venue: {venue}

## Current TikZ Code
```latex
{previous_tikz}
```

## Reviewer Feedback
{feedback_str}

## Requirements
1. Output the COMPLETE revised LaTeX document (\\documentclass to \\end{{document}})
2. Address ALL reviewer issues listed above
3. Keep the parts that were working well
4. Maintain the design guide standards
5. Do NOT add markdown code blocks around the output

Generate the revised TikZ code now:"""

    return prompt


def _build_fix_prompt(tikz_code: str, compile_error: str) -> str:
    """编译错误修复 prompt"""
    # 截取错误信息（避免太长）
    error_msg = compile_error[:800] if len(compile_error) > 800 else compile_error

    return f"""## Task
Fix the TikZ compilation error in the following LaTeX code.

## Current Code
```latex
{tikz_code}
```

## Compilation Error
```
{error_msg}
```

## Common Fixes
- Missing semicolons at end of \\draw or \\node commands
- Missing \\usetikzlibrary for used features (calc, fit, backgrounds, etc.)
- Incorrect calc syntax: use `($(A)!0.5!(B)$)` with correct dollar signs
- Unmatched braces or brackets
- Using features not loaded via \\usetikzlibrary

Output ONLY the fixed complete LaTeX document. No markdown code blocks."""


# ═══════════════════════════════════════════════════════════════
# 编译（Python 唯一的「硬约束」执行）
# ═══════════════════════════════════════════════════════════════

def _compile_tikz(tikz_code: str, fig_id: str, figures_dir: str,
                  max_retries: int = 1) -> Dict:
    """
    编译 TikZ 代码 → PDF + PNG。
    如果编译失败，返回空结果（不做创造性修改）。
    """
    os.makedirs(figures_dir, exist_ok=True)
    tmp_dir = tempfile.mkdtemp(prefix="tikz_")

    try:
        tex_path = os.path.join(tmp_dir, "fig.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tikz_code)

        pdflatex = _find_pdflatex()
        result = subprocess.run(
            [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "fig.tex"],
            cwd=tmp_dir, capture_output=True, text=True, timeout=30,
        )

        compiled_pdf = os.path.join(tmp_dir, "fig.pdf")
        if not os.path.exists(compiled_pdf) or os.path.getsize(compiled_pdf) < 1000:
            logger.error(f"[TikZCompiler] 编译失败: {result.stdout[-500:]}")
            return {"pdf_path": "", "png_path": "", "compile_error": result.stdout[-500:]}

        pdf_path = os.path.join(figures_dir, f"{fig_id}.pdf")
        shutil.copy2(compiled_pdf, pdf_path)

        png_path = os.path.join(figures_dir, f"{fig_id}.png")
        _pdf_to_png(compiled_pdf, png_path, tmp_dir)

        size = os.path.getsize(pdf_path)
        logger.info(f"[TikZCompiler] 编译成功: {pdf_path} ({size:,} bytes)")
        return {"pdf_path": pdf_path, "png_path": png_path}

    except subprocess.TimeoutExpired:
        logger.error("[TikZCompiler] 编译超时")
        return {"pdf_path": "", "png_path": "", "compile_error": "timeout"}
    except Exception as e:
        logger.error(f"[TikZCompiler] 异常: {e}")
        return {"pdf_path": "", "png_path": "", "compile_error": str(e)}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _pdf_to_png(pdf_path: str, png_path: str, tmp_dir: str):
    """PDF → PNG"""
    try:
        subprocess.run(
            ["pdftoppm", "-png", "-r", "200", pdf_path,
             os.path.join(tmp_dir, "fig")],
            capture_output=True, timeout=10,
        )
        tmp_png = os.path.join(tmp_dir, "fig-1.png")
        if os.path.exists(tmp_png):
            shutil.copy2(tmp_png, png_path)
            return
    except Exception:
        pass

    try:
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=200)
        if images:
            images[0].save(png_path)
            return
    except ImportError:
        pass

    logger.warning(f"[TikZCompiler] PNG 生成失败，仅 PDF 可用")


# ═══════════════════════════════════════════════════════════════
# 数据图 / 定性图（机械性工作，代码做）
# ═══════════════════════════════════════════════════════════════

def _gen_data_from_provided(fig_plan, figures_dir, venue):
    from tools.data_visualizer import generate_comparison_chart, generate_ablation_chart
    fig_id = fig_plan.get("fig_id", "fig")
    data = fig_plan.get("data", {})
    if fig_plan.get("fig_type") == "ablation":
        return generate_ablation_chart(data, figures_dir, fig_id, venue)
    return generate_comparison_chart(data, figures_dir, fig_id, venue)


def _gen_data_from_project(fig_plan, figures_dir, venue, project_path):
    from tools.experiment_explorer import explore_experiments, summary_to_dict
    from tools.data_visualizer import generate_comparison_chart, generate_ablation_chart

    fig_id = fig_plan.get("fig_id", "fig")
    fig_type = fig_plan.get("fig_type", "comparison")
    summary = explore_experiments(project_path)

    if fig_type == "ablation" and summary.ablation_data:
        ad = summary.ablation_data
        return generate_ablation_chart({
            "title": fig_plan.get("title", "Ablation Study"),
            "components": ad.components,
            "metrics": ad.metrics,
        }, figures_dir, fig_id, venue)

    if fig_type == "comparison" and summary.comparison_data:
        cd = summary.comparison_data
        return generate_comparison_chart({
            "title": fig_plan.get("title", "Performance Comparison"),
            "methods": cd.methods,
            "metrics": cd.metrics,
            "values": cd.values,
        }, figures_dir, fig_id, venue)

    return _gen_placeholder(fig_plan, figures_dir)


def _gen_qualitative_from_images(fig_plan, figures_dir, venue):
    from tools.data_visualizer import generate_image_grid
    return generate_image_grid(
        fig_plan.get("images", []),
        figures_dir,
        fig_plan.get("fig_id", "fig"),
        venue,
    )


def _gen_qualitative_from_project(fig_plan, figures_dir, venue, project_path):
    from tools.image_finder import find_qualitative_images, get_grid_image_paths, get_grid_titles
    from tools.data_visualizer import generate_image_grid

    qual_data = find_qualitative_images(project_path)
    image_paths = get_grid_image_paths(qual_data)
    if not image_paths:
        return _gen_placeholder(fig_plan, figures_dir)

    titles = get_grid_titles(qual_data)
    return generate_image_grid(image_paths, figures_dir,
                               fig_plan.get("fig_id", "fig"), venue,
                               n_cols=min(len(titles), 5),
                               titles=titles[:len(image_paths)])


# ═══════════════════════════════════════════════════════════════
# 占位符
# ═══════════════════════════════════════════════════════════════

def _gen_placeholder(fig_plan, figures_dir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig_id = fig_plan.get("fig_id", "fig")
    title = fig_plan.get("title", fig_plan.get("fig_type", ""))
    fig, ax = plt.subplots(figsize=(6, 2.5))
    ax.text(0.5, 0.5, f"[{fig_id}]\n{title}\n(Placeholder — requires data or LLM generation)",
            ha='center', va='center', fontsize=10, color='gray',
            transform=ax.transAxes)
    ax.axis('off')

    os.makedirs(figures_dir, exist_ok=True)
    pdf_path = os.path.join(figures_dir, f"{fig_id}.pdf")
    png_path = os.path.join(figures_dir, f"{fig_id}.png")
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight', facecolor='white')
    fig.savefig(png_path, format='png', bbox_inches='tight', dpi=150, facecolor='white')
    plt.close(fig)
    return {"pdf_path": pdf_path, "png_path": png_path}


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def _load_guide(filename: str) -> str:
    """加载 MD 引导文件"""
    path = os.path.join(_SKILL_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return f"[Guide file not found: {path}]"


def _call_llm(prompt: str, system_prompt: str, model_alias: str) -> str:
    """调用 LLM（自动路由到正确的 SDK）"""
    from api.openai_compatible import create_client_for_model

    client = create_client_for_model(
        model_alias,
        max_tokens=8192,
        temperature=0.3,
    )
    return client.query(prompt, system_prompt=system_prompt)


def _clean_tikz_output(raw: str) -> str:
    """清理 LLM 输出，提取纯 LaTeX 代码"""
    # 去掉 markdown 代码块包裹
    code = raw.strip()

    # 去掉 ```latex ... ``` 包裹
    if code.startswith("```"):
        # 去掉开头
        code = re.sub(r'^```(?:latex|tex)?\s*\n?', '', code)
        # 去掉结尾
        code = re.sub(r'\n?```\s*$', '', code)

    code = code.strip()

    # 确保 \documentclass 在开头
    if "\\documentclass" not in code:
        logger.warning("[TikZCleaner] 输出缺少 \\documentclass，尝试修补")
        if "\\begin{tikzpicture}" in code:
            code = (
                r"\documentclass[border=4pt]{standalone}" "\n"
                r"\usepackage{tikz}" "\n"
                r"\usetikzlibrary{positioning, arrows.meta, shapes.geometric, calc, fit, backgrounds}" "\n"
                r"\usepackage{amsmath,amssymb}" "\n"
                r"\begin{document}" "\n"
                + code + "\n"
                r"\end{document}"
            )

    return code


# ═══════════════════════════════════════════════════════════════
# v10.1: LLM TikZ 降级 — 数据图/定性图无数据时的 LLM 设计
# ═══════════════════════════════════════════════════════════════

def _gen_data_figure_llm(
    fig_plan: Dict,
    figures_dir: str,
    venue: str,
    text_model_alias: str,
) -> Dict:
    """
    LLM 用 TikZ 设计数据图/定性图的示意版本。
    当没有实际数据/图片时，让 LLM 创造性地设计一个 TikZ 示意图：
    - 消融图 → TikZ 表格 + 柱状图
    - 对比图 → TikZ 柱状图/雷达图
    - 定性图 → TikZ 对比布局示意图
    """
    fig_id = fig_plan.get("fig_id", "fig")
    fig_type = fig_plan.get("fig_type", "ablation")
    title = fig_plan.get("title", fig_type)
    caption = fig_plan.get("caption", "")

    guide = _load_guide("tikz_design_guide.md")
    examples = _load_guide("tikz_style_examples.md")
    data_guide = _load_guide("data_figure_guide.md")

    type_guidance = {
        "ablation": (
            "Design an ablation study TABLE figure using TikZ. "
            "Create a professional three-line table (booktabs style) showing component ablation results. "
            "Include columns for: component name, and 2-3 metrics. "
            "Use a row for 'Full model' and 3-4 rows for ablated variants. "
            "Bold the best results. Use \\usepackage{booktabs} for \\toprule/\\midrule/\\bottomrule."
        ),
        "comparison": (
            "Design a performance comparison BAR CHART figure using TikZ. "
            "Create a grouped bar chart comparing 5-6 methods across 2-3 datasets. "
            "Include a legend, axis labels, and error bars if applicable. "
            "Highlight the 'Ours' method with a distinct color/pattern."
        ),
        "qualitative": (
            "Design a qualitative comparison LAYOUT figure using TikZ. "
            "Create a grid layout showing input -> method comparisons -> results. "
            "Use placeholder boxes with descriptive labels (e.g., 'Input', 'Method A', 'Ours', 'Ground Truth'). "
            "Add arrows between columns to show the comparison flow."
        ),
    }.get(fig_type, "Design an academic paper figure using TikZ.")

    prompt = f"""## Task
Generate a complete, compilable LaTeX+TikZ document for an academic paper figure.
This is a {fig_type} figure but NO actual data/images are available yet.
Design a professional SCHEMATIC/TEMPLATE version that can be filled with real data later.

## Type-Specific Guidance
{type_guidance}

## Design Guide
{guide}

## Style Examples
{examples}

## Data Figure Guide
{data_guide}

## Figure Specification
- **Figure ID**: {fig_id}
- **Type**: {fig_type}
- **Title**: {title}
- **Caption**: {caption}
- **Target Venue**: {venue}

## Requirements
1. Output a COMPLETE standalone LaTeX document (\\documentclass to \\end{{document}})
2. The figure must look professional and publication-ready even as a template
3. Use realistic placeholder data/values (not "xxx" or "???")
4. Follow the design guide color scheme and typography rules
5. Size: ~16cm wide for double-column, ~8cm for single-column

Generate the TikZ code now:"""

    system_prompt = (
        "You are an expert TikZ developer for top-tier academic paper figures. "
        "You write clean, compilable LaTeX+TikZ code.\n"
        "Output ONLY the complete LaTeX document code, starting from \\documentclass. "
        "Do NOT wrap in markdown code blocks. Do NOT add any explanation outside the code."
    )

    logger.info(f"[FigureGen] LLM 生成数据图 TikZ: {fig_id} ({fig_type})")
    tikz_code = _call_llm(prompt, system_prompt, text_model_alias)
    tikz_code = _clean_tikz_output(tikz_code)

    result = _compile_tikz(tikz_code, fig_id, figures_dir)

    # 编译失败则 LLM 自动修复 1 次
    if not result.get("pdf_path") and result.get("compile_error"):
        logger.info(f"[FigureGen] 数据图编译失败，LLM 自动修复: {fig_id}")
        fix_prompt = _build_fix_prompt(tikz_code, result["compile_error"])
        fixed_code = _call_llm(fix_prompt, system_prompt, text_model_alias)
        fixed_code = _clean_tikz_output(fixed_code)

        if fixed_code and "\\documentclass" in fixed_code:
            result = _compile_tikz(fixed_code, fig_id, figures_dir)
            if result.get("pdf_path"):
                tikz_code = fixed_code
                logger.info(f"[FigureGen] 数据图自动修复成功: {fig_id}")

    if result.get("pdf_path"):
        tikz_src_path = os.path.join(figures_dir, f"{fig_id}_source.tex")
        with open(tikz_src_path, "w", encoding="utf-8") as f:
            f.write(tikz_code)
        result["tikz_source"] = tikz_src_path
        result["tikz_code"] = tikz_code
        result["generated_by"] = "llm_tikz_fallback"
    else:
        # LLM 也失败了，最后兜底：占位符
        logger.warning(f"[FigureGen] LLM TikZ 降级也失败，占位符: {fig_id}")
        result = _gen_placeholder(fig_plan, figures_dir)
        result["generated_by"] = "placeholder_after_llm_failure"

    return result


def _find_pdflatex() -> str:
    """自动探测 pdflatex 路径"""
    # 1. 环境变量指定
    env_path = os.environ.get("PDFLATEX_PATH", "")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2. which 查找
    try:
        r = subprocess.run(
            ["which", "pdflatex"], capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass

    # 3. 常见路径回退
    candidates = [
        "/usr/local/texlive/2026/bin/x86_64-linux/pdflatex",
        "/usr/local/texlive/2025/bin/x86_64-linux/pdflatex",
        "/usr/local/texlive/2024/bin/x86_64-linux/pdflatex",
        "/usr/bin/pdflatex",
        "/usr/local/bin/pdflatex",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c

    # 4. 最后兜底（让 subprocess 报错）
    return "pdflatex"
