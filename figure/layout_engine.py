# -*- coding: utf-8 -*-
"""
布局引擎 v9.2 (Layout Engine)

输入: modules + connections + template_name + design_constraints
输出: 确定性 TikZ 代码（完整 standalone LaTeX 文档）

核心改进（vs v9.1 BFS）:
1. 使用布局模板计算位置（而非固定间距 BFS）
2. 创新点模块视觉放大
3. 分组框精确包围（无重叠）
4. 边缘自适应箭头（避免穿过节点）
5. 视觉重心平衡
"""

import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple

from figure.layout_templates import (
    NodeSpec, EdgeSpec, GroupSpec, Position,
    select_template, get_template,
)

logger = logging.getLogger(__name__)


def generate_tikz_from_plan(
    fig_plan: Dict,
    figures_dir: str,
    venue: str = "IEEE TCSVT",
) -> Dict:
    """
    从 plan 生成 TikZ 架构图。

    Args:
        fig_plan: 图表计划 dict（含 modules, connections, groups）
        figures_dir: 输出目录
        venue: 目标 venue

    Returns:
        {"pdf_path": "...", "png_path": "..."}
    """
    fig_id = fig_plan.get("fig_id", "fig")
    modules = fig_plan.get("modules", [])
    connections = fig_plan.get("connections", [])
    groups = fig_plan.get("groups", [])
    template_name = fig_plan.get("layout_template", "")

    if not modules:
        logger.warning(f"[LayoutEngine] {fig_id} 无模块，跳过")
        return _fallback_result(fig_plan, figures_dir)

    # 转为规格对象
    nodes = [
        NodeSpec(
            id=m["id"],
            label=m.get("label", m["id"]),
            is_innovation=m.get("is_innovation", False),
            group=m.get("group", ""),
        )
        for m in modules
    ]

    edges = [
        EdgeSpec(
            from_id=c["from"],
            to_id=c["to"],
            label=c.get("label", ""),
        )
        for c in connections
    ]

    group_specs = [
        GroupSpec(
            id=g["id"],
            label=g.get("label", ""),
            module_ids=g.get("module_ids", []),
        )
        for g in groups
    ]

    # 选择模板并计算位置
    template = select_template(nodes, edges, template_name)
    positions = template.compute_positions(nodes, edges, group_specs)

    # 生成 TikZ 代码
    tikz_lines = _render_tikz(nodes, edges, group_specs, positions)

    # 编译
    return _compile_tikz(tikz_lines, fig_id, figures_dir)


# ═══════════════════════════════════════════════════════════════
# TikZ 渲染
# ═══════════════════════════════════════════════════════════════

def _render_tikz(
    nodes: List[NodeSpec],
    edges: List[EdgeSpec],
    groups: List[GroupSpec],
    positions: Dict[str, Position],
) -> List[str]:
    """将节点位置渲染为 TikZ 代码行"""
    lines = []

    # 1. 节点
    for node in nodes:
        pos = positions.get(node.id)
        if not pos:
            continue

        style = "innov" if node.is_innovation else "regular"
        label = _escape_latex(node.label)

        # 创新点节点用更大的 minimum width
        if node.is_innovation:
            w = f"{node.width:.1f}cm"
            lines.append(
                f"  \\node[{style}, minimum width={w}] ({node.id}) "
                f"at ({pos.x:.1f}, {pos.y:.1f}) {{{label}}};"
            )
        else:
            lines.append(
                f"  \\node[{style}] ({node.id}) "
                f"at ({pos.x:.1f}, {pos.y:.1f}) {{{label}}};"
            )

    # 2. 箭头
    for edge in edges:
        label = _escape_latex(edge.label)
        lbl_node = ""
        if label:
            lbl_node = f" node[lbl] {{{label}}}"
        lines.append(f"  \\draw[arr] ({edge.from_id}) --{lbl_node} ({edge.to_id});")

    # 3. 分组框
    for group in groups:
        mids = group.module_ids
        if len(mids) < 2:
            continue
        glabel = _escape_latex(group.label)
        fit_nodes = "".join(f"({mid})" for mid in mids)
        lines.append(
            f"  \\node[group, fit={fit_nodes}, "
            f"label={{[font=\\sffamily\\scriptsize, text=black!50]above:{glabel}}}] {{}};"
        )

    return lines


def _escape_latex(text: str) -> str:
    """转义 LaTeX 特殊字符"""
    if not text:
        return ""
    # 先将反斜杠替换为占位符，避免后续替换破坏 \textbackslash{} 中的花括号
    text = text.replace("\\", "\x00BACKSLASH\x00")
    for ch, esc in [("&", "\\&"), ("%", "\\%"), ("$", "\\$"),
                    ("#", "\\#"), ("_", "\\_"), ("{", "\\{"),
                    ("}", "\\}"), ("~", "\\textasciitilde{}"),
                    ("^", "\\textasciicircum{}")]:
        text = text.replace(ch, esc)
    text = text.replace("\x00BACKSLASH\x00", "\\textbackslash{}")
    return text


# ═══════════════════════════════════════════════════════════════
# 编译
# ═══════════════════════════════════════════════════════════════

def _find_pdflatex() -> str:
    """动态查找 pdflatex 路径"""
    import shutil
    # 1. 环境变量
    p = os.environ.get("PDFLATEX_PATH", "")
    if p and os.path.isfile(p):
        return p
    # 2. which 查找
    p = shutil.which("pdflatex")
    if p:
        return p
    # 3. 常见路径
    for candidate in [
        "/usr/local/texlive/2026/bin/x86_64-linux/pdflatex",
        "/usr/local/texlive/2025/bin/x86_64-linux/pdflatex",
        "/usr/local/bin/pdflatex",
        "/usr/bin/pdflatex",
    ]:
        if os.path.isfile(candidate):
            return candidate
    return "pdflatex"  # 兜底：依赖 PATH


def _compile_tikz(tikz_lines: List[str], fig_id: str, figures_dir: str) -> Dict:
    """编译 TikZ 代码为 PDF + PNG"""
    os.makedirs(figures_dir, exist_ok=True)

    tikz_body = "\n".join(tikz_lines)

    tex_content = r"""\documentclass[border=3pt]{standalone}
\usepackage{tikz}
\usetikzlibrary{positioning, arrows.meta, shapes.geometric, calc, fit}
\usepackage{amsmath,amssymb}
\begin{document}
\begin{tikzpicture}[
  innov/.style={draw, rounded corners=2mm, minimum width=2.8cm, minimum height=1.0cm,
                fill=orange!20, draw=orange!70!black, line width=1.2pt,
                align=center, font=\sffamily\small\bfseries},
  regular/.style={draw, rounded corners=2mm, minimum width=2.2cm, minimum height=0.85cm,
                  fill=blue!8, draw=black!40, line width=0.6pt,
                  align=center, font=\sffamily\small},
  arr/.style={-Stealth, thick, color=black!70},
  group/.style={draw=black!30, dashed, rounded corners=3mm, inner sep=6pt},
  lbl/.style={font=\sffamily\scriptsize, color=black!50, fill=white, inner sep=1pt},
  node distance=0.6cm and 1.2cm,
]
""" + tikz_body + r"""
\end{tikzpicture}
\end{document}
"""

    tmp_dir = tempfile.mkdtemp(prefix="tikz_")
    try:
        tex_path = os.path.join(tmp_dir, "fig.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_content)

        pdflatex = _find_pdflatex()
        result = subprocess.run(
            [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "fig.tex"],
            cwd=tmp_dir, capture_output=True, text=True, timeout=30,
        )

        compiled_pdf = os.path.join(tmp_dir, "fig.pdf")
        if not os.path.exists(compiled_pdf) or os.path.getsize(compiled_pdf) < 1000:
            logger.error(f"[LayoutEngine] TikZ 编译失败: {result.stdout[-300:]}")
            return {"pdf_path": "", "png_path": ""}

        pdf_path = os.path.join(figures_dir, f"{fig_id}.pdf")
        shutil.copy2(compiled_pdf, pdf_path)

        png_path = os.path.join(figures_dir, f"{fig_id}.png")
        try:
            subprocess.run(
                ["pdftoppm", "-png", "-r", "200", compiled_pdf,
                 os.path.join(tmp_dir, "fig")],
                capture_output=True, timeout=10,
            )
            tmp_png = os.path.join(tmp_dir, "fig-1.png")
            if os.path.exists(tmp_png):
                shutil.copy2(tmp_png, png_path)
            else:
                _pdf_to_png_fallback(pdf_path, png_path)
        except Exception:
            _pdf_to_png_fallback(pdf_path, png_path)

        logger.info(f"[LayoutEngine] TikZ 编译成功: {pdf_path}")
        return {"pdf_path": pdf_path, "png_path": png_path}

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _pdf_to_png_fallback(pdf_path: str, png_path: str):
    """PDF → PNG 降级方案"""
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=200)
        if images:
            images[0].save(png_path)
    except ImportError:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 1, figsize=(7, 3))
        ax.text(0.5, 0.5, "TikZ figure generated\n(see PDF for vector output)",
                ha='center', va='center', fontsize=10, color='gray')
        ax.axis('off')
        fig.savefig(png_path, dpi=150, facecolor='white')
        plt.close(fig)


def _fallback_result(fig_plan: Dict, figures_dir: str) -> Dict:
    """生成失败时的占位结果"""
    fig_id = fig_plan.get("fig_id", "fig")
    return {"pdf_path": "", "png_path": ""}
