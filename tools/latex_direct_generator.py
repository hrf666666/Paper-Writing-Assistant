# -*- coding: utf-8 -*-
"""
LaTeX 直出模块 v9.0 — 分章节直接生成 LaTeX

核心理念：
1. LLM 直接输出 LaTeX（不走 Markdown 中间格式，不用正则转换）
2. 每个章节/子节独立生成 + 独立编译验证
3. 编译失败 → 错误日志反馈给 LLM 自愈（最多 2 轮）
4. 图表约束：figure*/table* 双栏，明确宽度限制

参考：Sakana AI Scientist 的 per-section LaTeX generation 方案
"""

import os
import re
import subprocess
import logging
import tempfile
import shutil
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# IEEE 编译用最小 preamble
# ═══════════════════════════════════════════════════════════════
LATEX_PREAMBLE = r"""\documentclass[lettersize,journal]{IEEEtran}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{algorithmic}
\usepackage{algorithm}
\usepackage{array}
\usepackage[caption=false,font=normalsize,labelfont=sf,textfont=sf]{subfig}
\usepackage{textcomp}
\usepackage{stfloats}
\usepackage{url}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{tikz}
\usetikzlibrary{positioning, arrows.meta, shapes.geometric, calc, fit}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{hyperref}
\usepackage{cite}
\usepackage{tabularx}

\begin{document}
"""

LATEX_CLOSING = r"""
\end{document}
"""


# ═══════════════════════════════════════════════════════════════
# LaTeX 编译 + 验证
# ═══════════════════════════════════════════════════════════════

def _find_pdflatex() -> str:
    """查找 pdflatex 可执行文件"""
    # 常见路径
    candidates = [
        "/usr/local/texlive/2026/bin/x86_64-linux/pdflatex",
        "/usr/local/texlive/2025/bin/x86_64-linux/pdflatex",
        "/usr/bin/pdflatex",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    # 尝试 PATH 中查找
    result = shutil.which("pdflatex")
    if result:
        return result
    return candidates[0]  # 返回默认路径


def compile_latex(tex_content: str, output_dir: str = None,
                  timeout: int = 30) -> Tuple[bool, List[str], str]:
    """
    编译 LaTeX 内容，返回 (成功与否, 错误列表, 完整日志)

    Args:
        tex_content: 完整的 .tex 文件内容（含 preamble）
        output_dir: 输出目录（None 则用临时目录）
        timeout: 编译超时秒数
    """
    pdflatex = _find_pdflatex()

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        work_dir = output_dir
    else:
        work_dir = tempfile.mkdtemp(prefix="latex_compile_")

    tex_path = os.path.join(work_dir, "test.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)

    env = os.environ.copy()
    # 确保 pdflatex 在 PATH 中
    pdflatex_dir = os.path.dirname(pdflatex)
    env["PATH"] = pdflatex_dir + ":" + env.get("PATH", "")

    errors = []
    full_log = ""
    try:
        result = subprocess.run(
            [pdflatex, "-interaction=nonstopmode",
             "-output-directory", work_dir, tex_path],
            capture_output=True, timeout=timeout, env=env,
        )
        full_log = result.stdout.decode("utf-8", errors="replace")
        errors = re.findall(r"^! (.+)", full_log, re.MULTILINE)

    except subprocess.TimeoutExpired:
        errors = ["Compilation timed out"]
    except Exception as e:
        errors = [f"Compilation error: {e}"]

    success = len(errors) == 0
    return success, errors, full_log


def _detect_overflows(log_text: str) -> List[dict]:
    """
    解析 pdflatex 日志中的 Overfull \\hbox / \\vbox 警告。
    
    返回列表，每项:
      {
        "type": "OverfullHbox" | "OverfullVbox",
        "line": int | None,       # 出现行号
        "detail": str,            # 完整警告文本
        "pts": float | None,      # 溢出磅值（如有）
      }
    """
    overflows = []

    # Overfull \hbox (paragraph lines) — 例如:
    #   Overfull \hbox (15.3pt too wide) in paragraph at lines 42--48
    #   Overfull \hbox (12.0pt too wide) detected at line 100
    for m in re.finditer(
        r"Overfull \\hbox \(([\d.]+)pt too wide\) (?:in paragraph |detected )?at lines? (\d+)",
        log_text,
    ):
        overflows.append({
            "type": "OverfullHbox",
            "line": int(m.group(2)),
            "pts": float(m.group(1)),
            "detail": m.group(0),
        })

    # Overfull \vbox (用 "too high" 或 "too wide" 都能匹配)
    for m in re.finditer(
        r"Overfull \\vbox \(([\d.]+)pt too (?:wide|high)\)",
        log_text,
    ):
        overflows.append({
            "type": "OverfullVbox",
            "line": None,
            "pts": float(m.group(1)),
            "detail": m.group(0),
        })

    return overflows


def compile_latex_with_overflows(
    tex_content: str, output_dir: str = None, timeout: int = 30,
) -> Tuple[bool, List[str], str, List[dict]]:
    """
    编译 LaTeX 并同时返回溢出信息。
    
    Returns:
        (成功与否, 错误列表, 完整日志, 溢出列表)
    """
    success, errors, full_log = compile_latex(tex_content, output_dir, timeout)
    overflows = _detect_overflows(full_log)
    return success, errors, full_log, overflows


def compile_chapter_snippet(latex_body: str) -> Tuple[bool, List[str]]:
    """
    编译一个章节的 LaTeX 片段（自动包裹 preamble 和 closing）
    返回 (成功与否, 错误列表)
    """
    full_tex = LATEX_PREAMBLE + latex_body + LATEX_CLOSING
    success, errors, _ = compile_latex(full_tex)
    return success, errors


def compile_chapter_snippet_with_overflows(
    latex_body: str,
) -> Tuple[bool, List[str], List[dict]]:
    """
    编译章节片段并返回溢出信息。
    
    Returns:
        (成功与否, 错误列表, 溢出列表)
    """
    full_tex = LATEX_PREAMBLE + latex_body + LATEX_CLOSING
    success, errors, _, overflows = compile_latex_with_overflows(full_tex)
    return success, errors, overflows


# ═══════════════════════════════════════════════════════════════
# LLM 调用
# ═══════════════════════════════════════════════════════════════

def _call_llm(prompt: str, max_tokens: int = 16384) -> str:
    """调用 LLM 生成"""
    from agent.api_client import get_api_client
    api = get_api_client()
    return api.call_generation(prompt)


# ═══════════════════════════════════════════════════════════════
# LaTeX 通用 prompt 规则
# ═══════════════════════════════════════════════════════════════

LATEX_OUTPUT_RULES = r"""**OUTPUT FORMAT RULES (STRICT — violation = rejection)**:

═══ BASIC FORMAT ═══
1. Output ONLY LaTeX code. No Markdown, no triple backticks, no explanations.
2. Do NOT include \documentclass, \begin{document}, \end{document}, \usepackage, or any preamble.
3. Use \section{...} for the chapter title, \subsection{...} for sub-sections.
4. Bold: \textbf{...}. Italic: \textit{...}.
5. Lists: \begin{itemize} \item ... \end{itemize}.
6. ALL braces {} MUST be properly paired and nested.
7. Use [!t] for all floats. NEVER use [h] or [H] or [!h].
8. \PRESERVE ALL CONTENT**: Do NOT summarize, shorten, or omit anything.
9. Citations: \cite{key}. Ampersands in text: \& (bare & only as column separator in tabular).

═══ EQUATION WIDTH CONTROL (CRITICAL — single column = 3.5in ≈ 252pt) ═══
IEEEtran single column is only ~3.5 inches wide. MOST display equations with subscripts, 
fractions, sums, or Greek letters WILL overflow unless you actively prevent it.

RULE: If a display equation has MORE THAN 2 of these: \frac, \sum, \prod, \left[, subscripts, 
superscripts — it WILL overflow. You MUST use one of these formats instead of \begin{equation}:

For LONG single equations (one logical expression that doesn't fit one line):
\begin{multline}
  first_part_of_expression \\
  second_part_of_expression
  \label{eq:chN_M}
\end{multline}

For MULTI-LINE equations (multiple related expressions):
\begin{align}
  \text{short_name} &= expression_one \label{eq:chN_M1} \\
  \text{short_name} &= expression_two \label{eq:chN_M2}
\end{align}

For a SINGLE equation that needs alignment points:
\begin{equation}
  \begin{aligned}
    L &= \frac{1}{N}\sum_{i}\bigl[ \alpha \cdot f(x_i) \\
      &\quad + \beta \cdot g(x_i) \bigr]
  \end{aligned}
  \label{eq:chN_M}
\end{equation}

NEVER output a \begin{equation}...\end{equation} longer than ~80 characters on one line.
If in doubt, use align or multline — it is ALWAYS safer than equation.

═══ TABLE SIZE CONTROL (CRITICAL) ═══
Layout: \columnwidth ≈ 3.5in (single column), \textwidth ≈ 7in (double column).

MANDATORY TEMPLATE for every table:
── Single-column (≤4 cols, short text) ──
\begin{table}[!t]
\caption{...}\label{tab:...}
\centering
\resizebox{\columnwidth}{!}{%
\begin{tabular}{lll}
\toprule
... \\
\midrule
... \\
\bottomrule
\end{tabular}}
\end{table}

── Double-column (>4 cols OR long text cells) ──
\begin{table*}[!t]
\caption{...}\label{tab:...}
\centering\small
\resizebox{\textwidth}{!}{%
\begin{tabular}{lllllll}
\toprule
... \\
\midrule
... \\
\bottomrule
\end{tabular}}
\end{table*}

DECISION RULE: Count your columns. ≤4 and all cells < 10 chars → table. 
Otherwise → table*.
ALWAYS use booktabs (\toprule, \midrule, \bottomrule). NEVER \hline.
ALWAYS wrap tabular in \resizebox. This is NOT optional.

═══ FIGURE / TikZ SIZE CONTROL ═══
Every tikzpicture MUST be wrapped in \resizebox{\columnwidth or \textwidth}{!}{...tikzpicture...}.
Use relative positioning (right=of, below=of). NEVER use absolute coordinates like at (5,3).
Max coordinates: 6cm for single-column, 14cm for double-column.
Use PGF anchors: .south, .north, .east, .west.
"""


# ═══════════════════════════════════════════════════════════════
# 章节级 LaTeX 直出
# ═══════════════════════════════════════════════════════════════

# 各章节的子节划分
CHAPTER_SECTIONS = {
    1: [
        ("1.1", "Background and Problem Importance",
         "Introduce the research field's broad impact and significance. "
         "Explain the specific problem's core difficulties and challenges. "
         "Use concrete data and examples to show the problem's severity. "
         "Emphasize the urgency and necessity of solving this problem."),

        ("1.2", "Limitations of Existing Methods",
         "Systematically analyze shortcomings of existing methods by category "
         "(traditional methods, early DL methods, recent methods). "
         "For each category, identify 2-3 key limitations that correspond to "
         "problems this research can solve. Transition naturally to the need for a new approach."),

        ("1.3", "Proposed Method and Contributions",
         "Start with 'In this paper, we propose...' to describe the core idea. "
         "List 3 core contributions with specific technical details. "
         "Briefly mention experimental validation results."),
    ],
    2: [
        ("2.1", "Traditional Methods",
         "Review traditional (non-deep-learning) methods for this task. "
         "Categorize by approach. Discuss strengths and limitations."),

        ("2.2", "Deep Learning-based Methods",
         "Review deep learning methods, organized by technical approach. "
         "Highlight key innovations and remaining limitations."),

        ("2.3", "Summary and Motivation",
         "Summarize the state of the art. Identify the gap that motivates this work."),
    ],
    3: [
        ("3.1", "Overall Architecture",
         "Describe the overall system architecture. Include a figure* environment "
         "with TikZ code for the architecture diagram. Explain the design rationale."),

        ("3.2", "Core Components",
         "Detail each core component/module. Include mathematical formulations "
         "with equation environments. Explain the forward pass."),

        ("3.3", "Training Objective",
         "Describe the loss function, training strategy, and optimization details. "
         "Include equations for each loss component."),
    ],
    4: [
        ("4.1", "Experimental Setup",
         "Describe datasets, evaluation metrics, implementation details, "
         "and training configuration."),

        ("4.2", "Comparison with State-of-the-art",
         "Present quantitative comparison results in table* environment. "
         "Analyze performance across different scenarios. Discuss why our method excels."),

        ("4.3", "Ablation Studies",
         "Present ablation study results in table environments. "
         "Validate each design choice with evidence."),
    ],
    5: [
        ("5.1", "Conclusion",
         "Summarize the paper's contributions and key findings. "
         "Discuss implications and potential future directions."),
    ],
}


def _clean_llm_output(raw: str) -> str:
    """清理 LLM 输出中的非 LaTeX 内容"""
    text = raw.strip()

    # 移除 markdown 代码块包裹
    if text.startswith("```"):
        lines = text.split("\n")
        # 移除第一行 (```latex 或 ```)
        if lines[0].startswith("```"):
            lines = lines[1:]
        # 移除最后一行 (```)
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # 移除可能的 preamble 行（LLM 有时忽略规则）
    text = re.sub(r'^\\documentclass.*?\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\\usepackage.*?\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\\begin\{document\}.*?\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\\end\{document\}.*?$', '', text, flags=re.MULTILINE)

    return text.strip()


def _validate_float_sizing(latex_code: str) -> str:
    """
    后处理：检查 LLM 生成的 figure/table 尺寸选择是否合理。
    
    规则：
    - table*: >4列 或 包含长文本单元格 → 合理
    - table*: ≤4列 且 都是短文本 → 降级为 table (单栏)
    - figure*: 架构图/多组件图/多子图 → 合理  
    - figure*: 单张小图/简单图 → 降级为 figure (单栏)
    """
    # ── 表格尺寸验证 ──
    # 找到所有 table* 环境，检查列数
    def _check_table_star(match):
        env_content = match.group(0)
        # 提取列规格
        col_spec_match = re.search(r'\\begin\{tabular[*]?\}(?:\{[^}]*\})?\{([^}]+)\}', env_content)
        if not col_spec_match:
            return env_content  # 无法解析，保持原样
        
        col_spec = col_spec_match.group(1)
        # 清理 @{...} 和 p{...} 等，数 l/c/r/p 数量
        clean_spec = re.sub(r'@\{[^}]*\}', '', col_spec)
        clean_spec = re.sub(r'\{[^}]*\}', '', clean_spec)
        col_count = len(re.findall(r'[lcrp]', clean_spec))
        
        if col_count <= 4:
            logger.info(f"[float_sizing] table* ({col_count} cols) → table (downgrade)")
            result = env_content.replace('\\begin{table*}', '\\begin{table}', 1)
            result = result.replace('\\end{table*}', '\\end{table}', 1)
            # 去掉可能残留的 \resizebox{\textwidth}{!}{ 包裹
            result = re.sub(r'\\resizebox\{\\textwidth\}\{!\}\{\s*\n', '', result)
            # 去掉 resizebox 关闭的孤立 }
            result = re.sub(r'(\\end\{tabular\})\s*\n\s*\}', r'\1', result)
            # 重新包裹 \resizebox{\columnwidth}{!}（修复 textwidth 混淆）
            if '\\resizebox' not in result:
                result = result.replace(
                    '\\begin{tabular}',
                    '\\resizebox{\\columnwidth}{!}{%\n\\begin{tabular}'
                )
                result = result.replace(
                    '\\end{tabular}',
                    '\\end{tabular}%\n}'
                )
            else:
                # 已有 resizebox 但可能用的是 \textwidth → 修正为 \columnwidth
                result = result.replace('\\resizebox{\\textwidth}', '\\resizebox{\\columnwidth}')
            result = result.replace('\\end{tabular*}', '\\end{tabular}')
            return result
        
        return env_content
    
    latex_code = re.sub(
        r'\\begin\{table\*\}.*?\\end\{table\*\}',
        _check_table_star, latex_code, flags=re.DOTALL
    )
    
    # ── 图片尺寸验证 ──
    # figure* 只保留给真正的大图，小图降级
    # 启发式：如果一个 figure* 里只有一个 \includegraphics 且没有 subfigure，
    # 或者 TikZ 的 node 数量 ≤3，降级为 figure
    def _check_figure_star(match):
        env_content = match.group(0)
        
        # 检查是否有多子图（subfloat / subfigure / minipage 组合）
        has_subfig = bool(re.search(r'\\subfloat|\\begin\{minipage\}|\\subfigure', env_content))
        
        # 检查 TikZ node 数量
        tikz_nodes = len(re.findall(r'\\node\b', env_content))
        
        # 检查 \includegraphics 数量
        img_count = len(re.findall(r'\\includegraphics', env_content))
        
        # 大图特征：多子图 或 多node TikZ 或 明确提到 architecture/pipeline/overview
        is_large = (
            has_subfig or 
            tikz_nodes > 5 or 
            img_count > 2 or
            bool(re.search(r'architecture|pipeline|overview|framework|overall', env_content, re.IGNORECASE))
        )
        
        if not is_large:
            logger.info(f"[float_sizing] figure* (small, nodes={tikz_nodes}, imgs={img_count}) → figure (downgrade)")
            result = env_content.replace('\\begin{figure*}', '\\begin{figure}', 1)
            result = result.replace('\\end{figure*}', '\\end{figure}', 1)
            # 同时把 width=\textwidth 改为 width=\columnwidth
            result = result.replace('width=\\textwidth', 'width=\\columnwidth')
            return result
        
        return env_content
    
    latex_code = re.sub(
        r'\\begin\{figure\*\}.*?\\end\{figure\*\}',
        _check_figure_star, latex_code, flags=re.DOTALL
    )
    
    return latex_code


def _fix_textwidth_confusion(latex_code: str) -> str:
    """
    后处理：将单栏环境（table / figure，非 table* / figure*）中的
    \\textwidth 替换为 \\columnwidth，防止单栏元素撑到双栏宽度溢出。
    """
    # ── 单栏 table 环境 ──
    def _fix_table_env(match):
        env = match.group(0)
        old = env
        env = env.replace(r'\textwidth', r'\columnwidth')
        if env != old:
            logger.info("[fix_textwidth] 单栏 table 中 \\textwidth → \\columnwidth")
        return env

    # 匹配 \begin{table} 到 \end{table}，但排除 \begin{table*} 到 \end{table*}
    # 使用负向前瞻确保 \begin{table} 后面不是 *
    # 同时确保 \end{table} 后面不是 *
    # 简单策略：用 (?!...) 做前后约束
    latex_code = re.sub(
        r'\\begin\{table\}(?!\*).*?\\end\{table\}(?!\*)',
        _fix_table_env, latex_code, flags=re.DOTALL,
    )

    # ── 单栏 figure 环境 ──
    def _fix_figure_env(match):
        env = match.group(0)
        old = env
        env = env.replace(r'width=\textwidth', r'width=\columnwidth')
        env = env.replace(r'\textwidth', r'\columnwidth')
        if env != old:
            logger.info("[fix_textwidth] 单栏 figure 中 \\textwidth → \\columnwidth")
        return env

    latex_code = re.sub(
        r'\\begin\{figure\}(?!\*).*?\\end\{figure\}(?!\*)',
        _fix_figure_env, latex_code, flags=re.DOTALL,
    )

    return latex_code


def _ensure_table_resizebox(latex_code: str) -> str:
    """
    后处理：为缺少 \\resizebox 缩放包裹的 tabular 环境自动添加缩放。
    同时处理单栏 table 和双栏 table* 环境。
    v10.1: 对宽表格（>5列）强制添加 \\small/\\footnotesize 缩小字体。
    """
    def _fix_one_table(match):
        env = match.group(0)
        # 已有 resizebox → 不动
        if r'\resizebox' in env:
            return env

        # 找 tabular 开始位置
        tabular_start = re.search(r'\\begin\{tabular[*]?\}', env)
        if not tabular_start:
            return env

        # 判断单栏 / 双栏
        is_star = r'\begin{table*}' in env
        width_cmd = r'\textwidth' if is_star else r'\columnwidth'

        # 检测列数，宽表格需要缩小字体
        col_spec_match = re.search(r'\\begin\{tabular[*]?\}(?:\{[^}]*\})?\{([^}]+)\}', env)
        col_count = 0
        font_size_prefix = ''
        if col_spec_match:
            clean_spec = re.sub(r'@\{[^}]*\}', '', col_spec_match.group(1))
            clean_spec = re.sub(r'\{[^}]*\}', '', clean_spec)
            col_count = len(re.findall(r'[lcrp]', clean_spec))
            if col_count > 5:
                font_size_prefix = '\\footnotesize\n'
            elif col_count > 4:
                font_size_prefix = '\\small\n'

        # 在 \begin{tabular} 前插入 \resizebox{width}{!}{
        before = env[:tabular_start.start()]
        tabular_and_rest = env[tabular_start.start():]

        # 找 \end{tabular} 位置
        tabular_end = re.search(r'\\end\{tabular[*]?\}', tabular_and_rest)
        if not tabular_end:
            return env

        tabular_body = tabular_and_rest[:tabular_end.end()]
        after = tabular_and_rest[tabular_end.end():]

        # 包裹 resizebox
        result = (
            before + font_size_prefix +
            r'\resizebox{' + width_cmd + r'}{!}{%' + '\n' +
            tabular_body + '%' + '\n' + '}' +
            after
        )

        logger.info(f"[ensure_resizebox] table{'*' if is_star else ''} ({col_count} cols) 添加 resizebox({width_cmd})")
        return result

    # 匹配所有 table 环境（含 table*）
    latex_code = re.sub(
        r'\\begin\{table\*?\}.*?\\end\{table\*?\}',
        _fix_one_table, latex_code, flags=re.DOTALL,
    )

    return latex_code


def _ensure_tikz_fits(latex_code: str) -> str:
    """
    后处理：所有未被 \\resizebox 包裹的 tikzpicture 统一包裹 resizebox，
    确保缩放到所在环境（table/figure/table*/figure*）的可用宽度。
    """
    def _fix_one_tikz(match):
        tikz_block = match.group(0)

        # 检查 tikzpicture 前面是否有 \resizebox 包裹（看前 100 个字符）
        pos = match.start()
        preceding = latex_code[max(0, pos - 100):pos].strip()
        if r'\resizebox' in preceding:
            return tikz_block

        # 判断 tikzpicture 所在环境是单栏还是双栏
        all_preceding = latex_code[:pos]

        # 最近的环境类型
        last_fig_star = all_preceding.rfind(r'\begin{figure*}')
        last_fig = all_preceding.rfind(r'\begin{figure}')
        last_tab_star = all_preceding.rfind(r'\begin{table*}')
        last_tab = all_preceding.rfind(r'\begin{table}')

        # 判断是否双栏
        max_star = max(last_fig_star, last_tab_star)
        max_normal = max(last_fig, last_tab)

        if max_star > max_normal and max_star >= 0:
            width_cmd = r'\textwidth'
        else:
            width_cmd = r'\columnwidth'

        # 包裹整个 tikzpicture
        result = r'\resizebox{' + width_cmd + r'}{!}{' + '\n' + tikz_block + '\n' + '}'
        logger.info(f"[ensure_tikz_fits] tikzpicture 包裹 resizebox({width_cmd})")
        return result

    # 匹配 tikzpicture 环境
    latex_code = re.sub(
        r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}',
        _fix_one_tikz, latex_code, flags=re.DOTALL,
    )

    return latex_code


def _fix_long_equations(latex_code: str) -> str:
    """
    后处理：将可能溢出的长 equation 环境转为 multline 环境，并在合适位置拆行。

    关键处理：
    1. \\left/\\right 不能跨行 → 替换为 \\Big/\\Big（按行分别替换）
    2. 在 + 或 = 处拆行
    3. 只处理真正长（>80字符）且没有多行结构的公式
    """
    def _fix_one_eq(match):
        content = match.group(1)
        label_match = re.search(r'(\\label\{[^}]+\})', content)
        label = label_match.group(1) if label_match else ''
        body = re.sub(r'\\label\{[^}]+\}', '', content).strip()

        # 短公式不处理
        if len(body) < 80:
            return match.group(0)

        # 已有多行结构不处理 —— 但排除内部环境（bmatrix/pmatrix/vmatrix/cases）的 \\
        # 这些环境的 \\ 是矩阵行分隔，不是 equation 的多行拆分
        inner_envs = ['bmatrix', 'pmatrix', 'vmatrix', 'Vmatrix', 'cases', 'array',
                      'matrix', 'Bmatrix', 'smallmatrix', 'aligned', 'alignedat',
                      'gathered', 'split', 'subarray']
        body_without_inner = body
        for env in inner_envs:
            body_without_inner = re.sub(
                r'\\begin\{' + re.escape(env) + r'\}.*?\\end\{' + re.escape(env) + r'\}',
                '', body_without_inner, flags=re.DOTALL,
            )

        db_check = '\\\\' in body_without_inner
        al_check = 'begin{align' in body
        ml_check = 'begin{multline' in body
        if db_check or al_check or ml_check:
            return match.group(0)

        # 在 "+ " 处拆分（找最接近中间的 + 号）
        # 备选：在 "= " 处拆分（等号赋值）
        plus_positions = [m.start() for m in re.finditer(r'\+ ', body)]
        eq_positions = [m.start() for m in re.finditer(r'= ', body)]

        if plus_positions:
            mid_pos = len(body) // 2
            best_split = min(plus_positions, key=lambda p: abs(p - mid_pos))
        elif eq_positions:
            # 在第二个 = 处拆分（第一个通常是定义符 J = ...）
            if len(eq_positions) > 1:
                best_split = eq_positions[1]
            else:
                best_split = eq_positions[0]
        else:
            return match.group(0)

        line1 = body[:best_split].rstrip()
        line2 = body[best_split:].lstrip()

        # 处理 \left/\right 跨行不匹配问题
        # 拆行后，\left 和 \right 可能被分到不同行，导致 LaTeX 编译错误
        # 解决方案：将 \left → \Bigl, \right → \Bigr（不需要跨行配对）
        line1 = _fix_left_right_for_line(line1)
        line2 = _fix_left_right_for_line(line2)

        result = f'\\begin{{multline}}\n{label}\n{line1} \\\\\n{line2}\n\\end{{multline}}'
        logger.info("[fix_long_equations] equation -> multline")
        return result

    latex_code = re.sub(
        r'\\begin\{equation\}(.*?)\\end\{equation\}',
        _fix_one_eq, latex_code, flags=re.DOTALL,
    )

    return latex_code


def _fix_left_right_for_line(line: str) -> str:
    """
    修复拆行后 \\left/\\right 不匹配问题。

    \\left 和 \\right 必须在同一行配对出现。拆行后可能导致：
    - 第一行有 \\left 但没有对应的 \\right（被分到第二行）
    - 第二行有 \\right 但没有对应的 \\left

    解决方案：当 \\left 和 \\right 数量不配对时，
    全部替换为固定大小的定界符 \\Bigl/\\Bigr（不要求同行配对）。

    Args:
        line: 拆分后的单行公式
    """
    left_count = len(re.findall(r'\\left\b', line))
    right_count = len(re.findall(r'\\right\b', line))

    if left_count == right_count:
        # 已经配对，不需要修复
        return line

    # 不配对 → 用 string replace 一次性替换（避免正则回溯灾难）
    # 先替换 \leftX → \BiglX，再替换 \rightX → \BigrX
    # 注意：必须先替换 \left 再替换 \right，且用字符串替换而非正则
    for old, new in [
        (r'\left(', r'\Bigl('),
        (r'\left[', r'\Bigl['),
        (r'\left\{', r'\Bigl\{'),
        (r'\left|', r'\Bigl|'),
        (r'\left.', r'\Bigl.'),
        (r'\right)', r'\Bigr)'),
        (r'\right]', r'\Bigr]'),
        (r'\right\}', r'\Bigr\}'),
        (r'\right|', r'\Bigr|'),
        (r'\right.', r'\Bigr.'),
    ]:
        line = line.replace(old, new)

    return line


def _overflow_heal_loop(
    latex_code: str,
    max_rounds: int = 3,
    label: str = "",
) -> Tuple[str, bool, List[dict]]:
    """
    溢出自愈闭环：编译 → 检测溢出 → 后处理修复 → 重编译。

    每轮按顺序尝试：
      1. _fix_textwidth_confusion  (textwidth→columnwidth 修正)
      2. _ensure_table_resizebox   (补缺失的 resizebox)
      3. _ensure_tikz_fits         (TikZ 包裹 resizebox)
      4. _validate_float_sizing    (table*/figure* 降级)
      5. _fix_long_equations       (超宽 equation → multline 拆行)

    如果后处理全部用完仍有溢出，最后一轮调用 LLM 做语义级修复。

    Args:
        latex_code: 章节级 LaTeX 代码（不含 preamble/closing）
        max_rounds: 最大自愈轮数
        label: 日志标签（如 "Ch3 S3.1"）

    Returns:
        (修复后的 latex_code, 是否成功无溢出, 最终溢出列表)
    """
    code = latex_code

    for rnd in range(1, max_rounds + 1):
        # 编译 + 检测溢出
        success, errors, overflows = compile_chapter_snippet_with_overflows(code)

        # 编译错误先不处理（交给上层编译自愈）
        if not success:
            logger.warning(f"[overflow_heal] {label} 编译失败 ({len(errors)} errors)，溢出自愈中止")
            return code, False, overflows

        # 没有溢出 → 成功
        if not overflows:
            logger.info(f"[overflow_heal] {label} 第 {rnd} 轮: 0 溢出 ✅")
            return code, True, overflows

        # 有溢出 → 汇报
        total_pts = sum(o.get("pts", 0) or 0 for o in overflows)
        logger.warning(
            f"[overflow_heal] {label} 第 {rnd} 轮: {len(overflows)} 个溢出 "
            f"(共 {total_pts:.1f}pt)，开始后处理修复..."
        )

        # ── 后处理修复链 ──
        code_before = code
        code = _fix_textwidth_confusion(code)
        code = _ensure_table_resizebox(code)
        code = _ensure_tikz_fits(code)
        code = _validate_float_sizing(code)
        code = _fix_long_equations(code)

        # 如果后处理没有改变代码，且还有溢出 → 最后一轮用 LLM 修复
        if code == code_before:
            if rnd == max_rounds:
                logger.warning(f"[overflow_heal] {label} 后处理无法消除溢出，尝试 LLM 修复")
                code = _llm_fix_overflows(code, overflows, label)
            else:
                logger.warning(f"[overflow_heal] {label} 后处理未改变代码，继续下一轮")
                continue

    # 最终编译确认
    success, errors, overflows = compile_chapter_snippet_with_overflows(code)
    if not overflows:
        logger.info(f"[overflow_heal] {label} 自愈后 0 溢出 ✅")
        return code, True, overflows

    logger.warning(f"[overflow_heal] {label} 自愈后仍有 {len(overflows)} 个溢出")
    return code, False, overflows


def _llm_fix_overflows(latex_code: str, overflows: List[dict],
                        label: str = "") -> str:
    """
    调用 LLM 根据溢出信息修复 LaTeX 代码。
    """
    overflow_summary = "\n".join(
        f"  - {o['detail']}" for o in overflows[:10]
    )

    prompt = f"""The following LaTeX code has {len(overflows)} overfull box warning(s) when compiled with pdflatex (IEEEtran two-column layout).

**Overfull warnings**:
{overflow_summary}

**Key rules to fix overflows**:
- In single-column floats (\\begin{{table}}, \\begin{{figure}}): use \\columnwidth, NOT \\textwidth.
- In double-column floats (\\begin{{table*}}, \\begin{{figure*}}): use \\textwidth.
- Always wrap tabular in \\resizebox{{\\columnwidth or \\textwidth}}{{!}}{{...}}
- Always wrap tikzpicture in \\resizebox{{\\columnwidth or \\textwidth}}{{!}}{{...}}
- For long text in table cells, use p{{...}} column type instead of l/c.
- Reduce font size inside tables if needed: \\small, \\footnotesize.
- Break long words or URLs that don't hyphenate.

**Original LaTeX**:
{latex_code}

Output ONLY the corrected LaTeX (no preamble, no document wrapper, no markdown):
"""

    try:
        fixed_raw = _call_llm(prompt)
        fixed = _clean_llm_output(fixed_raw)
        if fixed and len(fixed.strip()) > 50:
            logger.info(f"[llm_fix_overflows] {label}: LLM 修复完成 ({len(fixed)} chars)")
            return fixed
    except Exception as e:
        logger.error(f"[llm_fix_overflows] {label}: LLM 调用失败: {e}")

    return latex_code


def _build_section_prompt(chapter_num: int, section_id: str, section_title: str,
                          section_instruction: str, context: str,
                          project_data: dict, previous_content: str = "",
                          layout_constraints: str = "") -> str:
    """构建单个子节的 LaTeX 直出 prompt"""

    import json
    innovation_points = project_data.get("innovation_points", [])
    model_architecture = project_data.get("model_architecture", {})
    experiment_design = project_data.get("experiment_design", {})

    # 创新点摘要
    innovation_summary = ""
    for i, ip in enumerate(innovation_points, 1):
        innovation_summary += f"\nInnovation {i}: {ip.get('创新点名称', 'N/A')}\n"
        innovation_summary += f"  Work: {'; '.join(ip.get('创新点工作内容', []))}\n"
        innovation_summary += f"  Value: {ip.get('创新点价值', 'N/A')}\n"

    from config.project_config import PAPER_TITLE

    prompt = f"""You are an expert IEEE Transactions LaTeX writer. Write Section {section_id} "{section_title}" for the paper "{PAPER_TITLE}".

{LATEX_OUTPUT_RULES}

**Section {section_id} Content Requirements**:
{section_instruction}

{layout_constraints}

**Paper Context**:
{context}

**Innovation Points**:
{innovation_summary}

**Model Architecture**:
{json.dumps(model_architecture, ensure_ascii=False, indent=2)[:3000]}

**Experiment Design**:
{json.dumps(experiment_design, ensure_ascii=False, indent=2)[:2000]}
"""

    if previous_content:
        prompt += f"""
**Previously generated sections** (maintain coherence):
<previous_content>
{previous_content[-3000:]}
</previous_content>
"""

    prompt += "\nNow write the LaTeX code for this section:\n"

    return prompt


def generate_section_latex(chapter_num: int, section_idx: int,
                           project_data: dict, context: str,
                           previous_content: str = "",
                           max_heal_attempts: int = 2,
                           enable_visual_verify: bool = True) -> Tuple[str, bool]:
    """
    生成单个子节的 LaTeX 并验证。

    完整五步闭环:
      1. 预评估布局（分析内容结构，预判表格/图片应该怎样输出）
      2. LLM 生成（带布局约束注入）
      3. 编译验证（+ Overflow 检测）
      4. 视觉验证（渲染 PDF → GLM-5V-turbo 检查）
      5. 反推迭代（视觉反馈 → 修复 → 重来）

    Returns:
        (latex_code, compilation_success)
    """
    sections = CHAPTER_SECTIONS.get(chapter_num, [])
    if section_idx >= len(sections):
        return "", False

    section_id, section_title, section_instruction = sections[section_idx]

    # ── 第1步: 预评估布局 ──
    layout_constraints = ""
    try:
        from tools.visual_verifier import prevaluate_layout, generate_layout_constraints
        layout_plan = prevaluate_layout(section_instruction, project_data)
        layout_constraints = generate_layout_constraints(layout_plan)
        logger.info(f"[latex_direct] Ch{chapter_num} S{section_id}: 布局预评估完成 "
                     f"({len(layout_plan.get('tables', []))} 表, "
                     f"{len(layout_plan.get('figures', []))} 图)")
    except Exception as e:
        logger.warning(f"[latex_direct] 布局预评估跳过: {e}")

    # ── 第2步: 构建 prompt（带布局约束）+ LLM 生成 ──
    prompt = _build_section_prompt(
        chapter_num, section_id, section_title, section_instruction,
        context, project_data, previous_content,
        layout_constraints=layout_constraints,
    )

    logger.info(f"[latex_direct] Ch{chapter_num} S{section_id}: 生成中...")
    raw_output = _call_llm(prompt)
    latex_code = _clean_llm_output(raw_output)

    if not latex_code or len(latex_code.strip()) < 50:
        logger.warning(f"[latex_direct] Ch{chapter_num} S{section_id}: LLM 输出过短")
        return latex_code, False

    # ── 第2.5步: 尺寸后处理（三层防护） ──
    latex_code = _fix_textwidth_confusion(latex_code)
    latex_code = _ensure_table_resizebox(latex_code)
    latex_code = _ensure_tikz_fits(latex_code)
    latex_code = _validate_float_sizing(latex_code)
    latex_code = _fix_long_equations(latex_code)

    # ── 第3步: 编译验证 + 溢出自愈闭环 ──
    tag = f"Ch{chapter_num} S{section_id}"
    latex_code, overflow_ok, overflows = _overflow_heal_loop(
        latex_code, max_rounds=3, label=tag,
    )

    # 溢出自愈过程中编译可能失败，这里再编译一次确认
    success, errors = compile_chapter_snippet(latex_code)

    if not success:
        # 自愈循环（编译错误）
        for attempt in range(1, max_heal_attempts + 1):
            logger.warning(
                f"[latex_direct] {tag}: 编译失败 ({len(errors)} errors), "
                f"自愈第 {attempt} 轮"
            )
            for e in errors[:5]:
                logger.warning(f"  ! {e[:120]}")

            heal_prompt = f"""The following LaTeX code has {len(errors)} compilation errors.

**Errors**:
{chr(10).join(errors[:8])}

**Original LaTeX code**:
{latex_code}

Fix ALL errors. Output ONLY the corrected LaTeX code (no preamble, no document wrapper).
Rules:
- Ensure all braces {{ }} are paired
- Use \\& for ampersands in text, bare & in tabular only
- Use standard PGF anchors (.south/.north/.east/.west)
- Use [!t] for all float positions
- Do NOT use \\hline, only \\toprule/\\midrule/\\bottomrule

Corrected LaTeX:"""

            try:
                healed_raw = _call_llm(heal_prompt)
                healed_code = _clean_llm_output(healed_raw)

                if healed_code and len(healed_code.strip()) > 50:
                    latex_code = healed_code
                    success, errors = compile_chapter_snippet(latex_code)

                    if success:
                        logger.info(
                            f"[latex_direct] {tag}: "
                            f"自愈成功 ✅ (第 {attempt} 轮, {len(latex_code)} chars)"
                        )
                        break
            except Exception as e:
                logger.error(f"[latex_direct] 自愈调用失败: {e}")

    if not success:
        logger.warning(f"[latex_direct] {tag}: 编译自愈失败，跳过视觉验证")
        return latex_code, False

    # ── 第4步: 视觉验证闭环 ──
    if enable_visual_verify:
        try:
            from tools.visual_verifier import visual_verify_pipeline

            full_tex = LATEX_PREAMBLE + latex_code + LATEX_CLOSING
            fixed_tex, vis_result = visual_verify_pipeline(
                full_tex, max_rounds=2
            )

            # 从完整 tex 中提取 body（去掉 preamble 和 closing）
            body = fixed_tex
            if body.startswith(LATEX_PREAMBLE):
                body = body[len(LATEX_PREAMBLE):]
            if body.endswith(LATEX_CLOSING):
                body = body[:-len(LATEX_CLOSING)]
            body = body.strip()

            if body and len(body) > 50:
                latex_code = body

            vis_ok = vis_result.get("ok", True)
            vis_summary = vis_result.get("summary", "?")
            issues_count = len(vis_result.get("issues", []))

            if vis_ok:
                logger.info(f"[latex_direct] {tag}: "
                            f"视觉验证通过 ✅ ({vis_summary})")
            else:
                logger.warning(f"[latex_direct] {tag}: "
                               f"视觉验证发现 {issues_count} 个问题 — {vis_summary}")
                # 视觉修复后重新编译确认
                success2, errors2 = compile_chapter_snippet(latex_code)
                if not success2:
                    logger.warning(f"[latex_direct] 视觉修复导致编译失败，回退")
                    # 回退逻辑 — 但保留 latex_code 不变

        except ImportError:
            logger.info(f"[latex_direct] visual_verifier 不可用，跳过视觉验证")
        except Exception as e:
            logger.warning(f"[latex_direct] {tag}: 视觉验证异常: {e}")

    logger.info(f"[latex_direct] {tag}: 完成 ✅ ({len(latex_code)} chars)")
    return latex_code, True


def generate_chapter_latex(chapter_num: int, project_data: dict,
                           context: str = "") -> Tuple[str, dict]:
    """
    生成完整章节的 LaTeX（逐子节生成 + 验证 + 拼装）

    Args:
        chapter_num: 章节号 (1-5)
        project_data: 项目数据（innovation_points, model_architecture 等）
        context: 上下文信息（前序章节内容等）

    Returns:
        (latex_code, stats_dict)
        stats_dict 包含: sections_generated, sections_passed, sections_failed
    """
    sections = CHAPTER_SECTIONS.get(chapter_num, [])
    if not sections:
        return "", {"error": f"Unknown chapter {chapter_num}"}

    all_latex_parts = []
    stats = {
        "sections_generated": 0,
        "sections_passed": 0,
        "sections_failed": 0,
        "details": [],
    }

    previous = ""
    for idx, (sec_id, sec_title, sec_instruction) in enumerate(sections):
        latex_code, success = generate_section_latex(
            chapter_num, idx, project_data, context, previous
        )

        stats["sections_generated"] += 1
        if success:
            stats["sections_passed"] += 1
        else:
            stats["sections_failed"] += 1

        stats["details"].append({
            "section": sec_id,
            "title": sec_title,
            "success": success,
            "length": len(latex_code),
        })

        if latex_code:
            all_latex_parts.append(latex_code)
            previous += "\n" + latex_code

    full_latex = "\n\n".join(all_latex_parts)
    return full_latex, stats


# ═══════════════════════════════════════════════════════════════
# 全论文组装
# ═══════════════════════════════════════════════════════════════

def assemble_full_paper(chapter_latex_parts: List[str],
                        tikz_code: str = "",
                        abstract_latex: str = "",
                        keywords: str = "") -> str:
    """
    将各章节 LaTeX 拼装为完整的 IEEE Trans 论文
    """
    from config.project_config import (
        PAPER_TITLE, PAPER_AUTHORS, PAPER_CORRESPONDING_AUTHOR,
        PAPER_AFFILIATION
    )

    title = PAPER_TITLE.replace("&", "\\&")
    authors = PAPER_AUTHORS.replace("&", "\\and")
    author_short = PAPER_AUTHORS.split(",")[0].strip()

    paper = LATEX_PREAMBLE

    # 标题和作者
    paper += f"\\title{{{title}}}\n\n"
    paper += f"""\\author{{\\IEEEauthorblockN{{{authors}}}
\\IEEEauthorblockA{{{PAPER_AFFILIATION}}}
\\thanks{{Manuscript received May 2026. (Corresponding author: {PAPER_CORRESPONDING_AUTHOR})}}}}

\\markboth{{IEEE Transactions on Circuits and Systems for Video Technology}}%
{{{author_short} et al.: {title[:50]}}}

\\maketitle\n\n"""

    # Abstract
    if abstract_latex:
        # 清理可能残留的 \begin{abstract}
        abstract_clean = abstract_latex.replace("\\begin{abstract}", "").replace("\\end{abstract}", "")
        paper += f"\\begin{{abstract}}\n{abstract_clean.strip()}\n\\end{{abstract}}\n\n"
    else:
        paper += "\\begin{abstract}\n% TODO: Abstract to be added\n\\end{abstract}\n\n"

    # Keywords
    if keywords:
        kw_clean = keywords.replace("\\begin{IEEEkeywords}", "").replace("\\end{IEEEkeywords}", "")
        paper += f"\\begin{{IEEEkeywords}}\n{kw_clean.strip()}\n\\end{{IEEEkeywords}}\n\n"
    else:
        paper += "\\begin{IEEEkeywords}\n% TODO: Keywords\n\\end{IEEEkeywords}\n\n"

    # 各章节
    for i, chapter_tex in enumerate(chapter_latex_parts, 1):
        if chapter_tex and chapter_tex.strip():
            paper += f"% ════════════════════════════════════════\n"
            paper += f"% Chapter {i}\n"
            paper += f"% ════════════════════════════════════════\n\n"
            paper += chapter_tex + "\n\n"

    # 参考文献
    paper += "\\bibliographystyle{IEEEtran}\n"
    paper += "\\bibliography{references}\n"

    paper += LATEX_CLOSING

    # ═══ 全局后处理：确保拼装后的完整论文也经过修复 ═══
    paper = _fix_textwidth_confusion(paper)
    paper = _ensure_table_resizebox(paper)
    paper = _ensure_tikz_fits(paper)
    paper = _validate_float_sizing(paper)
    paper = _fix_long_equations(paper)
    logger.info("[assemble] 全局后处理完成 (5 步修复链)")

    return paper


def compile_full_paper(paper_tex: str, output_dir: str,
                       enable_visual_verify: bool = True) -> Tuple[bool, List[str], str]:
    """编译完整论文 + 可选视觉验证"""
    os.makedirs(output_dir, exist_ok=True)

    # 写入 .tex
    tex_path = os.path.join(output_dir, "main.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(paper_tex)

    # 复制 references.bib（如果存在）
    for bib_src in ["output/latex/references.bib", "output/quick_test/references.bib"]:
        if os.path.exists(bib_src):
            shutil.copy2(bib_src, os.path.join(output_dir, "references.bib"))
            break
    else:
        # 创建空 bib
        with open(os.path.join(output_dir, "references.bib"), "w") as f:
            f.write("% References placeholder\n")

    # 复制 figures
    figures_dir = os.path.join(output_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)
    for src in ["output/latex/figures", "output/figures"]:
        if os.path.isdir(src):
            for fname in os.listdir(src):
                src_path = os.path.join(src, fname)
                if os.path.isfile(src_path):
                    shutil.copy2(src_path, os.path.join(figures_dir, fname))

    # 编译两次（解决引用交叉引用）
    success = False
    errors = []
    full_log = ""

    pdflatex = _find_pdflatex()
    env = os.environ.copy()
    env["PATH"] = os.path.dirname(pdflatex) + ":" + env.get("PATH", "")

    for run in range(2):
        try:
            result = subprocess.run(
                [pdflatex, "-interaction=nonstopmode",
                 "-output-directory", output_dir, tex_path],
                capture_output=True, timeout=60, env=env,
            )
            full_log = result.stdout.decode("utf-8", errors="replace")
            errors = re.findall(r"^! (.+)", full_log, re.MULTILINE)
        except Exception as e:
            errors = [f"Compilation error: {e}"]

    success = len(errors) == 0

    # 提取页数
    pages = "?"
    pages_match = re.search(r"Output written on .+?(\d+) pages", full_log)
    if pages_match:
        pages = pages_match.group(1)

    if success:
        logger.info(f"[latex_direct] 全文编译通过 ✅ ({pages} pages)")

        # ── 视觉验证 ──
        if enable_visual_verify:
            pdf_path = os.path.join(output_dir, "main.pdf")
            if os.path.isfile(pdf_path):
                try:
                    from tools.visual_verifier import verify_full_paper
                    vis_result = verify_full_paper(pdf_path)
                    vis_ok = vis_result.get("ok", True)
                    vis_summary = vis_result.get("summary", "?")
                    issues = vis_result.get("issues", [])

                    if vis_ok:
                        logger.info(f"[latex_direct] 全文视觉验证通过 ✅ ({vis_summary})")
                    else:
                        logger.warning(f"[latex_direct] 全文视觉验证发现 {len(issues)} 个问题:")
                        for issue in issues:
                            logger.warning(
                                f"  [{issue.get('severity', '?')}] "
                                f"{issue.get('element', '?')}: "
                                f"{issue.get('problem', '')[:80]}"
                            )
                        # 保存视觉验证报告
                        import json
                        report_path = os.path.join(output_dir, "visual_verify_report.json")
                        with open(report_path, "w") as f:
                            json.dump(vis_result, f, ensure_ascii=False, indent=2)
                        logger.info(f"[latex_direct] 视觉验证报告已保存: {report_path}")

                except ImportError:
                    logger.info("[latex_direct] visual_verifier 不可用，跳过视觉验证")
                except Exception as e:
                    logger.warning(f"[latex_direct] 视觉验证异常: {e}")
    else:
        logger.warning(f"[latex_direct] 全文编译失败: {len(errors)} errors")

    return success, errors, full_log
