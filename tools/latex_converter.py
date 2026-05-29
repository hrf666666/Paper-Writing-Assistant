# -*- coding: utf-8 -*-
"""
Tool: LaTeX转换器 v9.0
将各章节Markdown内容转换为完整的IEEE期刊格式LaTeX论文代码

关键改进：
1. 模板对标 bare_jrnl_new_sample4.tex (IEEE TCSVT 标准)
2. 公式转换：\(...\) inline → $...$; \[...\] display → equation/align 环境
3. 章节级去重（跨章节检测重复section）
4. 清理所有Markdown残留（## Abstract, **Keywords:**, 中文标题等）
5. 表格转换改进：三线表，正确行数
6. 图片引用占位 → \includegraphics
"""

import os
import re
import logging
from typing import List, Tuple, Optional

from config.project_config import (
    PAPER_TITLE, OUTPUT_DIR, LATEX_TEMPLATE, ARTICLE_TYPE, get_article_type_info,
    PAPER_AUTHORS, PAPER_AFFILIATION, PAPER_CORRESPONDING_AUTHOR
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# IEEE 期刊模板（对标 bare_jrnl_new_sample4.tex）
# ═══════════════════════════════════════════════════════════════
LATEX_TEMPLATES = {
    "ieee_trans": r"""\documentclass[lettersize,journal]{IEEEtran}
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
\hyphenation{op-tical net-works semi-conduc-tor}

\begin{document}

\title{TITLE_PLACEHOLDER}

\author{AUTHOR_PLACEHOLDER
\thanks{Manuscript received DATE_PLACEHOLDER. This work was supported by Beihang University. (Corresponding author: Zhenglong Cui)}
\thanks{R. Huang and Z. Cui are with the School of Computer Science and Engineering, Beihang University, Beijing, China (e-mail: huangruifeng@buaa.edu.cn; czl@buaa.edu.cn).}}

\markboth{IEEE Transactions on Circuits and Systems for Video Technology}%
{AUTHOR_SHORT_PLACEHOLDER: TITLE_SHORT_PLACEHOLDER}

\maketitle

\begin{abstract}
ABSTRACT_PLACEHOLDER
\end{abstract}

\begin{IEEEkeywords}
KEYWORDS_PLACEHOLDER
\end{IEEEkeywords}

BODY_PLACEHOLDER

\bibliographystyle{IEEEtran}
\bibliography{references}

\end{document}
""",
    "acm_conf": r"""\documentclass[sigconf]{acmart}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{graphicx}
\usepackage{tikz}
\usetikzlibrary{positioning, arrows.meta, shapes.geometric, calc, fit}
\usepackage{booktabs}

\begin{document}

\title{TITLE_PLACEHOLDER}
\author{AUTHOR_PLACEHOLDER}

\maketitle

\begin{abstract}
ABSTRACT_PLACEHOLDER
\end{abstract}

BODY_PLACEHOLDER

\bibliographystyle{ACM-Reference-Format}
\bibliography{references}

\end{document}
""",
}


# ═══════════════════════════════════════════════════════════════
# 公式计数器
# ═══════════════════════════════════════════════════════════════
_equation_counter = 0


def _next_eq_label() -> str:
    global _equation_counter
    _equation_counter += 1
    return f"eq:eq{_equation_counter}"


def _reset_eq_counter():
    global _equation_counter
    _equation_counter = 0


# ═══════════════════════════════════════════════════════════════
# LLM 直接翻译 MD → LaTeX（替代正则转换）
# ═══════════════════════════════════════════════════════════════
def _convert_chapter_via_llm(md_chapter: str, chapter_num: int) -> str:
    """
    使用 LLM 将 Markdown 章节直接翻译为 LaTeX。
    这比正则替换更可靠，因为 LLM 理解上下文语义。

    返回空字符串表示失败（调用方应回退到 markdown_to_latex）。
    """
    try:
        from tools.base_tool import get_tool_api
        api = get_tool_api()
    except Exception:
        return ""

    if not md_chapter or len(md_chapter.strip()) < 100:
        return ""

    # 章节名映射
    chapter_names = {
        1: "Introduction", 2: "Related Work", 3: "Methodology",
        4: "Experiments", 5: "Conclusion"
    }
    ch_name = chapter_names.get(chapter_num, f"Chapter {chapter_num}")

    prompt = f"""You are an expert LaTeX formatter. Convert the following Markdown chapter into valid IEEE Transactions LaTeX code.

**Rules** (STRICT):
1. Use \\section{{}} for top-level headings (the chapter title is "{ch_name}")
2. Use \\subsection{{}} for ## headings, \\subsubsection{{}} for ### headings
3. Mathematics: keep $...$ and $$...$$ as-is (already LaTeX syntax). For display math, wrap in \\begin{{equation}}...\\end{{equation}} with \\label{{eq:ch{chapter_num}_N}}
4. Tables: use \\begin{{table*}}[!t] for wide tables (>5 cols), \\begin{{table}}[!t] for narrow. Use booktabs (\\toprule/\\midrule/\\bottomrule). Include \\caption{{}} and \\label{{}}.
5. Bold: \\textbf{{...}}, Italic: \\textit{{...}}
6. Lists: \\begin{{itemize}} \\item ... \\end{{itemize}}
7. Citations: convert <citation>...</citation> to \\cite{{key}} where key is a cleaned version of the content
8. Do NOT use \\documentclass, \\begin{{document}}, \\end{{document}}, \\bibliography, or any preamble commands
9. Do NOT include the chapter \\section title if it's already in the content as a # heading — convert it naturally
10. Do NOT use Chinese characters — remove any Chinese text
11. Use \\& for ampersands in text (NOT in tabular environments where & is column separator)
12. Figures: use \\begin{{figure*}}[!t] for double-column figures
13. Make sure ALL braces {{ }} are properly paired and nested
14. **IMPORTANT: Preserve ALL content exactly. Do NOT summarize, shorten, or omit any paragraph, table, or formula.**
15. Output ONLY the LaTeX code, no explanation

**Input Markdown chapter** (convert EVERYTHING, do not skip):
```
{md_chapter}
```"""

    try:
        result = api.call_generation(prompt)
        if not result or len(result.strip()) < 50:
            return ""

        # 清理可能的 markdown 包裹
        result = result.strip()
        if result.startswith("```"):
            lines = result.split("\n")
            result = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        # 移除可能的 \documentclass 等前导内容
        result = re.sub(r'^.*?(?=\\\\section\{|\\\\subsection\{|\\\\begin\{)', '', result, flags=re.DOTALL, count=1)

        logger.info(f"[latex_converter] 章节 {chapter_num} LLM翻译完成: {len(result)} 字符")
        return result.strip()

    except Exception as e:
        logger.warning(f"[latex_converter] 章节 {chapter_num} LLM翻译异常: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════
# Markdown → LaTeX 转换（正则回退方案）
# ═══════════════════════════════════════════════════════════════
def markdown_to_latex(md_text: str) -> str:
    """将Markdown格式文本转换为LaTeX格式（v9.3 公式转换增强版）"""

    latex = md_text

    # ── 0. 预处理：清理中文子标题 ──
    latex = _clean_chinese_in_sections(latex)

    # ═══ v9.3 关键改进：优先保护所有原始公式内容 ═══
    # 在转换之前先保护原始公式，避免后续处理破坏公式结构
    _math_protection_store = []
    _original_math_store = []

    def _protect_original_display_math(match):
        """保护原始显示公式 $$...$$"""
        _original_math_store.append(('display', match.group(1)))
        return f"__ORIGMATH_{len(_original_math_store) - 1}__"

    def _protect_original_inline_math(match):
        """保护原始行内公式 $...$"""
        _original_math_store.append(('inline', match.group(1)))
        return f"__ORIGMATH_{len(_original_math_store) - 1}__"

    # ── 保护顺序很重要：先长后短，先显式标记后隐式标记 ──
    # 1. 保护 \[...\] 显示公式（LaTeX 标准标记）
    latex = re.sub(r'\\\[(.+?)\\\]', _protect_original_display_math, latex, flags=re.DOTALL)
    # 2. 保护 \(...\) 行内公式（LaTeX 标准标记）
    latex = re.sub(r'\\\((.+?)\\\)', _protect_original_inline_math, latex, flags=re.DOTALL)
    # 3. 保护 $$...$$ 显示公式（Markdown/TeX 通用标记）
    latex = re.sub(r'\$\$(.+?)\$\$', _protect_original_display_math, latex, flags=re.DOTALL)
    # 4. 保护 $...$ 行内公式（严格：不含换行、不含 $）
    latex = re.sub(r'(?<!\$)\$(?!\$)([^$\n]+?)(?<!\$)\$(?!\$)', _protect_original_inline_math, latex)
    # 5. 保护 <formula>...</formula> 标记（视为显示公式）
    latex = re.sub(r'<formula>(.+?)</formula>', _protect_original_display_math, latex, flags=re.DOTALL)

    # ── 1. 统一转换所有 __ORIGMATH_ 标记：按 math_type 区分行内/显示 ──
    def convert_math_marker(match):
        idx = int(match.group(1))
        math_type, formula = _original_math_store[idx]
        formula = formula.strip()
        if not formula:
            return ''

        # 行内公式：直接包裹为 $...$
        if math_type == 'inline':
            return f'${formula}$'

        # 显示公式：按复杂度选择 equation 或 align 环境
        # 清理可能残留的 aligned 嵌套
        cleaned = formula.replace('\\begin{aligned}', '').replace('\\end{aligned}', '')

        # 含多行对齐符或子环境时用 align
        if '\\\\' in cleaned or '\\begin{' in cleaned or '\\aligned' in cleaned:
            return f'\\begin{{align}}\n{cleaned}\n\\end{{align}}'

        label = _next_eq_label()
        return f'\\begin{{equation}}\n\\label{{{label}}}\n{cleaned}\n\\end{{equation}}'

    latex = re.sub(r'__ORIGMATH_(\d+)__', convert_math_marker, latex)

    # ═══ 关键：在公式转换后立即保护所有数学内容 ═══
    # 这样后续的 * → \textit{} 转换不会影响公式内容
    _math_protection_store = []

    def _protect_math(match):
        _math_protection_store.append(match.group(0))
        return f"__MATHPROT_{len(_math_protection_store) - 1}__"

    # 保护 equation/align 环境块
    latex = re.sub(r'\\begin\{equation\}.*?\\end\{equation\}', _protect_math, latex, flags=re.DOTALL)
    latex = re.sub(r'\\begin\{align\}.*?\\end\{align\}', _protect_math, latex, flags=re.DOTALL)
    # 保护行内公式 $...$
    latex = re.sub(r'\$[^$]+\$', _protect_math, latex)

    # ── 6. 去除连续的相同标题（支持 1-6 级 Markdown 标题） ──
    lines = latex.split('\n')
    cleaned_lines = []
    prev_section = ""
    for line in lines:
        stripped = line.strip()
        sec_match = re.match(r'^\\section\{(.+?)\}', stripped)
        hdr_match = re.match(r'^#{1,6}\s+(.+)$', stripped)
        if sec_match:
            title = sec_match.group(1)
            if title.lower() == prev_section.lower():
                continue
            prev_section = title
        elif hdr_match:
            title = hdr_match.group(1)
            if title.lower() == prev_section.lower():
                continue
            prev_section = title
        else:
            if not stripped.startswith('\\subsection') and not stripped.startswith('\\subsubsection'):
                prev_section = ""
        cleaned_lines.append(line)
    latex = '\n'.join(cleaned_lines)

    # ── 7. 处理章节标题：移除数字前缀（支持 1-6 级） ──
    def clean_section_number(match):
        prefix = match.group(1)
        rest = match.group(2)
        # 修复: 原正则 \d+(?:\.\d+)* 要求点后必须跟数字，无法匹配 "1. Introduction"
        cleaned = re.sub(r'^\d+\.?\d*(?:\.\d+)*\s+', '', rest)
        return f'{prefix} {cleaned}'

    latex = re.sub(r'^(#{1,6})\s+(\d+\.?\d*(?:\.\d+)*\s+.+)$', clean_section_number, latex, flags=re.MULTILINE)

    # ── 7.5 清理 \\section{N. Title} 和 \\subsection{N.N Title} 中的手动编号 ──
    # LLM 可能生成 "\\section{4. Experiments}" 或 "\\section{1. Introduction}" 格式
    def _strip_latex_heading_number(match):
        cmd = match.group(1)  # section / subsection / subsubsection
        title = match.group(2)
        cleaned = re.sub(r'^\d+\.?\d*\s+', '', title)
        return f'\\{cmd}{{{cleaned}}}'

    latex = re.sub(
        r'\\(section|subsection|subsubsection)\{(\d+\.?\d*\s+.+?)\}',
        _strip_latex_heading_number, latex
    )
    # 同时处理 \paragraph{N.N.N Title.} 格式
    latex = re.sub(
        r'\\(paragraph|subparagraph)\{(\d+\.?\d*\s+.+?)\}',
        _strip_latex_heading_number, latex
    )

    # ── 8. Markdown 标题 → LaTeX 命令（支持 1-6 级，#### → \paragraph） ──
    latex = re.sub(r'^# (.+)$', r'\\section{\1}', latex, flags=re.MULTILINE)
    latex = re.sub(r'^## (.+)$', r'\\subsection{\1}', latex, flags=re.MULTILINE)
    latex = re.sub(r'^### (.+)$', r'\\subsubsection{\1}', latex, flags=re.MULTILINE)
    latex = re.sub(r'^#### (.+)$', r'\\paragraph{\1.}', latex, flags=re.MULTILINE)
    latex = re.sub(r'^##### (.+)$', r'\\subparagraph{\1.}', latex, flags=re.MULTILINE)
    latex = re.sub(r'^###### (.+)$', r'\\subparagraph{\1.}', latex, flags=re.MULTILINE)

    # ── 8.5 清理 Step 8 刚生成的 \section{N. Title} 中的手动编号 ──
    # Step 8 将 # 1. Introduction 转为 \section{1. Introduction}，此处清除编号
    def _strip_post_heading_number(match):
        cmd = match.group(1)
        title = match.group(2)
        cleaned = re.sub(r'^\d+\.?\d*(?:\.\d+)*\s+', '', title)
        return f'\\{cmd}{{{cleaned}}}'

    latex = re.sub(
        r'\\(section|subsection|subsubsection|paragraph|subparagraph)\{(\d+\.?\d*(?:\.\d+)*\s+[^}]+)\}',
        _strip_post_heading_number, latex
    )

    # ── 8.6 章节标题括号平衡修复 ──
    # LLM 可能生成 \subsection{Title (} 或 \subsection{Title (text} 等不平衡括号
    def _fix_heading_brackets(match):
        prefix = match.group(1)   # e.g. "section" / "subsection"
        title = match.group(2)
        # 检查圆括号平衡
        open_p = title.count('(')
        close_p = title.count(')')
        if open_p > close_p:
            title = title.rstrip() + ')' * (open_p - close_p)
        elif close_p > open_p:
            title = '(' * (close_p - open_p) + title
        # 检查方括号平衡
        open_b = title.count('[')
        close_b = title.count(']')
        if open_b > close_b:
            title = title.rstrip() + ']' * (open_b - close_b)
        elif close_b > open_b:
            title = '[' * (close_b - open_b) + title
        # 截断以 ) 结尾后跟的冗余中文内容 (如 "三层角信号分解)")
        title = re.sub(r'\)\s*[\(（].*$', ')', title)
        return f'\\{prefix}{{{title}}}'

    latex = re.sub(
        r'\\(section|subsection|subsubsection|paragraph|subparagraph)\{([^}]+)}',
        _fix_heading_brackets, latex
    )

    # ── 8.7 章节内标题层级归一化 ──
    # IEEE Trans 论文中 section 内只允许 subsection 和 subsubsection，
    # 如果某章内第一个子标题是 subsubsection（跳过 subsection），自动降级为 subsection
    def _normalize_heading_levels(text):
        lines = text.split('\n')
        in_section = False
        first_sub_in_section = True
        result = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('\\section{'):
                in_section = True
                first_sub_in_section = True
            elif in_section and (stripped.startswith('\\subsection{') or stripped.startswith('\\subsubsection{')):
                if first_sub_in_section:
                    # 第一个子标题应该是 \subsection
                    if stripped.startswith('\\subsubsection{'):
                        line = line.replace('\\subsubsection{', '\\subsection{', 1)
                    first_sub_in_section = False
                # 后续子标题保持原样（subsection/subsubsection 都合法）
            result.append(line)
        return '\n'.join(result)

    latex = _normalize_heading_levels(latex)

    # ── 9. 加粗和斜体（此时数学内容已被保护，不会误转换） ──
    # 先保护 table* 和 tabular* 中的 *
    _star_protection_store = []
    def _protect_star(match):
        _star_protection_store.append(match.group(0))
        return f"__STARPROT_{len(_star_protection_store) - 1}__"

    latex = re.sub(r'(?:table|tabular)\*', _protect_star, latex)

    latex = re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', latex)
    latex = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'\\textit{\1}', latex)

    # 恢复 table* 和 tabular*
    for i, part in enumerate(_star_protection_store):
        latex = latex.replace(f"__STARPROT_{i}__", part)

    # ── 10. <citation> 标记 → \cite{} ──
    def replace_citation(match):
        try:
            import ast
            keywords = ast.literal_eval(match.group(1))
            cite_key = re.sub(r'[^a-zA-Z0-9]', '', "_".join(
                keywords[0] if isinstance(keywords[0], list) else keywords
            )[:30])
            return f'\\cite{{{cite_key}}}'
        except Exception:
            return f'\\cite{{?}}'

    latex = re.sub(r'<citation>(.*?)</citation>', replace_citation, latex, flags=re.DOTALL)

    # ── 11. Markdown 表格 → LaTeX 三线表 ──
    _table_counter = [0]  # mutable counter for closures

    def replace_table(match):
        table_text = match.group(0)
        rows = table_text.strip().split('\n')
        if len(rows) < 3:
            return table_text

        header = [cell.strip() for cell in rows[0].split('|') if cell.strip()]
        data_lines = []
        for line in rows[2:]:
            row = [cell.strip() for cell in line.split('|') if cell.strip()]
            if row:
                data_lines.append(row)

        if not header:
            return table_text

        col_count = len(header)
        _table_counter[0] += 1
        table_id = _table_counter[0]

        # 从表头生成 caption（取前 3 列名）
        caption_text = ' '.join(header[:3])
        if len(caption_text) > 60:
            caption_text = caption_text[:57] + '...'

        # 根据列数选择表格类型和列规格
        if col_count > 5:
            col_spec = 'l' * col_count  # 使用 l 避免 p{0.13} 导致溢出
            latex_table = '\\begin{table*}[!t]\n'
            latex_table += '\\small\n'
            # 注意: \resizebox 的 { 必须在 \end{tabular*} 后用 } 关闭
            resizebox_open = '\\resizebox{\\textwidth}{!}{\n'
            resizebox_close = '}\n'
            env_close = '\\end{table*}'
        elif col_count > 3:
            col_spec = 'l' * col_count
            latex_table = '\\begin{table}[!t]\n'
            resizebox_open = ''
            resizebox_close = ''
            env_close = '\\end{table}'
        else:
            col_spec = 'l' * col_count
            latex_table = '\\begin{table}[!t]\n'
            resizebox_open = ''
            resizebox_close = ''
            env_close = '\\end{table}'

        latex_table += f'\\caption{{{caption_text}.}}\n'
        latex_table += f'\\label{{tab:table{table_id}}}\n'
        latex_table += '\\centering\n'

        if col_count > 5:
            # 宽表格: resizebox → tabular* → 关 tabular* → 关 resizebox → 关 table*
            latex_table += resizebox_open
            latex_table += f'\\begin{{tabular*}}{{\\textwidth}}{{@{{\\extracolsep{{\\fill}}}}{col_spec}}}\n'
        elif col_count > 3:
            # 中等表格使用 tabular*
            latex_table += f'\\begin{{tabular*}}{{\\linewidth}}{{@{{\\extracolsep{{\\fill}}}}{col_spec}}}\n'
        else:
            latex_table += f'\\begin{{tabular}}{{{col_spec}}}\n'

        latex_table += '\\toprule\n'
        latex_table += ' & '.join(header) + ' \\\\\n'
        latex_table += '\\midrule\n'

        for row in data_lines:
            padded = row[:col_count]
            while len(padded) < col_count:
                padded.append('')
            latex_table += ' & '.join(padded) + ' \\\\\n'

        latex_table += '\\bottomrule\n'
        # 清理表格内容中的 Unicode 符号和问题字符
        latex_table = latex_table.replace('✗', '$\\times$')
        latex_table = latex_table.replace('✓', '\\checkmark')
        latex_table = latex_table.replace('→', '$\\rightarrow$')
        latex_table += f'\\end{{tabular*}}\n' if col_count > 3 else '\\end{tabular}\n'
        latex_table += resizebox_close  # 关闭 \resizebox{...}{!}{
        latex_table += env_close
        return latex_table

    latex = re.sub(
        r'(\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|\n?)+)',
        replace_table, latex, flags=re.MULTILINE
    )

    # 表格转换后，保护 table* 和 tabular* 中的 *
    latex = re.sub(r'(?:table|tabular)\*', _protect_star, latex)

    # ── 12. 列表：包裹在 itemize 中 ──
    # 查找连续的 - 开头行并包裹
    def wrap_itemize(match):
        items = match.group(0)
        lines = items.split('\n')
        wrapped = '\\begin{itemize}\n'
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('- '):
                wrapped += f'  \\item {stripped[2:]}\n'
            elif stripped.startswith('\\item '):
                wrapped += f'  {stripped}\n'
        wrapped += '\\end{itemize}'
        return wrapped

    latex = re.sub(r'((?:^- .+$\n?){2,})', wrap_itemize, latex, flags=re.MULTILINE)
    # 单行列表
    latex = re.sub(r'^- (.+)$', r'\\begin{itemize}\\item \1\\end{itemize}', latex, flags=re.MULTILINE)

    # ── 13. 代码块 ──
    latex = re.sub(r'```(\w+)?\n(.*?)```', r'\\begin{verbatim}\n\2\n\\end{verbatim}', latex, flags=re.DOTALL)

    # ── 14. 特殊字符保护与处理 ──
    protected_parts = []
    def protect_latex(match):
        protected_parts.append(match.group(0))
        return f"__PROTECTED_{len(protected_parts) - 1}__"

    # 保护已有 LaTeX 命令
    latex = re.sub(r'\\(?:cite|textbf|textit|label|ref|includegraphics|centering|caption|frac|sum|text|int|mathbb|mathcal|mathrm|mathbf|hat|tilde|bar|vec|dot|ddot|left|right|nonumber|hline|toprule|midrule|bottomrule|Big|bigg|paragraph|subparagraph)\{[^}]*\}', protect_latex, latex)
    latex = re.sub(r'\\(?:begin|end)\{[^}]*\}', protect_latex, latex)

    # 处理特殊字符（只转义非标题位置的 #）
    # ── 保护 tabular/tabular* 环境中的 & 列分隔符 ──
    _amp_protect = []
    def _protect_amp(m):
        _amp_protect.append(m.group(0))
        return f'__AMP_{len(_amp_protect) - 1}__'
    latex = re.sub(r'\\begin\{tabular\*?\}.*?\\end\{tabular\*?\}', _protect_amp, latex, flags=re.DOTALL)
    # 转义裸 &
    latex = latex.replace('&', '\\&')
    # 恢复 tabular 中的 &
    for i, v in enumerate(_amp_protect):
        latex = latex.replace(f'__AMP_{i}__', v)
    # 转义 % 但保护已有的 LaTeX 注释行（行首 % 或 \%）
    # 策略：先保护 \%, 然后转义裸 %, 最后恢复
    _pct_protect = []
    def _protect_pct(m):
        _pct_protect.append(m.group(0))
        return f'__PCT_{len(_pct_protect)-1}__'
    # 保护已转义的 \%
    latex = re.sub(r'\\%', _protect_pct, latex)
    # 保护 resizebox/table 内部的 %（在 { 和 } 之间的注释 %）
    latex = re.sub(r'(?<=\{)%', _protect_pct, latex)
    # 转义剩余裸 %
    latex = latex.replace('%', '\\%')
    # 恢复保护
    for i, v in enumerate(_pct_protect):
        latex = latex.replace(f'__PCT_{i}__', v)
    # 只转义行中间的 #，不转义行首的 #（标题已在步骤 8 处理）
    latex = re.sub(r'([^\\])#', r'\1\\#', latex)
    latex = re.sub(r'^#(?![#])', '\\#', latex, flags=re.MULTILINE)

    # 清理异常字符
    latex = latex.replace('\ufffd', '')  # U+FFFD replacement character
    latex = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', latex)  # Control chars

    # 恢复保护的内容
    for i, part in enumerate(protected_parts):
        latex = latex.replace(f"__PROTECTED_{i}__", part)

    # 恢复保护后，textbf/textit 等命令内可能含有未转义的 &
    # 需要再次保护 tabular 环境，然后只转义残余的裸 &（不是 \&）
    _amp_protect2 = []
    def _protect_amp2(m):
        _amp_protect2.append(m.group(0))
        return f'__AMP2_{len(_amp_protect2) - 1}__'
    latex = re.sub(r'\\begin\{tabular\*?\}.*?\\end\{tabular\*?\}', _protect_amp2, latex, flags=re.DOTALL)
    # 先保护已转义的 \&，再转义裸 &，最后恢复
    _escaped_amp = []
    def _protect_escaped_amp(m):
        _escaped_amp.append(m.group(0))
        return f'__ESCAPED_AMP_{len(_escaped_amp) - 1}__'
    latex = re.sub(r'\\&', _protect_escaped_amp, latex)
    latex = latex.replace('&', '\\&')
    for i, v in enumerate(_escaped_amp):
        latex = latex.replace(f'__ESCAPED_AMP_{i}__', v)
    for i, v in enumerate(_amp_protect2):
        latex = latex.replace(f'__AMP2_{i}__', v)

    # ═══ 恢复数学内容保护 ═══
    for i, part in enumerate(_math_protection_store):
        latex = latex.replace(f"__MATHPROT_{i}__", part)

    # ── 15. 最终残留清理 ──
    latex = re.sub(r'__PROTECTED_\d+__?', '', latex)
    latex = re.sub(r'__MATHPROT_\d+__?', '', latex)
    latex = re.sub(r'\*\*([^*]+?)\*\*', r'\\textbf{\1}', latex)
    latex = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'\\textit{\1}', latex)
    # 清理行首残留的 *（列表项标记）
    latex = re.sub(r'^\*\s+', '', latex, flags=re.MULTILINE)
    latex = re.sub(r'\[\?\]', '', latex)
    latex = re.sub(r'\[ref\]', '', latex, flags=re.IGNORECASE)
    latex = re.sub(r'</?formula>', '', latex)
    latex = re.sub(r'</?citation>', '', latex)
    # 清理 <citation> 清除后残留的双空格（或更多连续空格）
    latex = re.sub(r'  +', ' ', latex)
    latex = re.sub(r'##\s*Abstract\s*', '', latex)
    latex = re.sub(r'\*\*Keywords?:\*\*\s*', '', latex)
    latex = re.sub(r'\\section\{\s*\}', '', latex)
    latex = re.sub(r'\\subsection\{\s*\}', '', latex)
    latex = re.sub(r'\\paragraph\{\s*\}\.', '', latex)
    latex = re.sub(r'\\subparagraph\{\s*\}\.', '', latex)
    
    # v9.2: 移除硬编码 AI 词汇替换和括号转换
    # 这些现在由学术风格检查器（硬约束）和风格指南（柔性引导）处理
    
    # 在所有星号转换完成后，恢复 table* 和 tabular*
    for i, part in enumerate(_star_protection_store):
        latex = latex.replace(f"__STARPROT_{i}__", part)
    _star_protection_store.clear()
    latex = _fix_unpaired_environments(latex)

    return latex


def _clean_chinese_in_sections(text: str) -> str:
    """清理 LaTeX 或 Markdown 标题中的中文内容"""
    # 匹配 Markdown 标题中的中文
    def clean_md_heading(match):
        prefix = match.group(1)
        content = match.group(2)
        # 如果包含中文字符，移除中文部分
        if re.search(r'[\u4e00-\u9fff]', content):
            # 尝试保留数字前缀和英文部分
            cleaned = re.sub(r'[\u4e00-\u9fff]+[^\w\s]*', '', content).strip()
            # 如果清理后为空，保留原内容（后续LLM会处理）
            if not cleaned:
                cleaned = content
            return f'{prefix} {cleaned}'
        return match.group(0)

    text = re.sub(r'^(#{1,3})\s+(.+)$', clean_md_heading, text, flags=re.MULTILINE)
    return text


# ═══════════════════════════════════════════════════════════════
# 章节组装
# ═══════════════════════════════════════════════════════════════
def _deduplicate_sections(body_parts: List[str]) -> List[str]:
    """
    跨章节去重：检测重复的 \section 标题，保留第一次出现

    修复 B3：只跳过重复标题行本身，保留章节内容
    """
    seen_sections = set()
    result = []
    for part in body_parts:
        lines = part.split('\n')
        cleaned_lines = []
        skip_current_line = False

        for line in lines:
            stripped = line.strip()
            sec_match = re.match(r'^\\section\{(.+?)\}', stripped)
            if sec_match:
                title = sec_match.group(1).lower()
                if title in seen_sections:
                    # 这是重复的section标题，只跳过这一行
                    logger.info(f"[latex_converter] 移除重复section标题: {sec_match.group(1)}")
                    continue  # 跳过重复标题，但继续处理后续内容
                else:
                    seen_sections.add(title)
                    cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)

        if cleaned_lines:
            result.append('\n'.join(cleaned_lines))

    return result


def assemble_latex_paper(chapters: List[str], tikz_code: str = "",
                         abstract: str = "", keywords: str = "",
                         authors: str = None) -> str:
    """将各章节组装为完整的IEEE格式LaTeX论文"""

    _reset_eq_counter()

    # 使用配置中的作者信息（如果未提供）
    if authors is None or authors == "Anonymous":
        authors = PAPER_AUTHORS

    article_info = get_article_type_info()
    template_name = LATEX_TEMPLATE if LATEX_TEMPLATE in LATEX_TEMPLATES else "ieee_trans"
    template = LATEX_TEMPLATES[template_name]

    # 转换各章节
    body_parts = []
    for i, chapter in enumerate(chapters):
        if not chapter or not chapter.strip():
            continue
        # 优先使用 LLM 直接翻译 MD → LaTeX（跳过正则转换的 bug）
        latex_chapter = _convert_chapter_via_llm(chapter, i + 1)
        if not latex_chapter:
            # LLM 翻译失败，回退到正则转换
            logger.warning(f"[latex_converter] 章节 {i+1} LLM翻译失败，回退到正则转换")
            latex_chapter = markdown_to_latex(chapter)
        body_parts.append(latex_chapter)

    # 跨章节去重
    body_parts = _deduplicate_sections(body_parts)

    # 如果有TikZ架构图代码，插入到Methodology章节
    if tikz_code:
        # IEEEtran 双栏排版：架构图用 figure* 占满两栏宽度
        tikz_figure = f"""
\\begin{{figure*}}[!t]
\\centering
{tikz_code}
\\caption{{Overall architecture of the proposed method.}}
\\label{{fig:architecture}}
\\end{{figure*}}
"""
        # 插入到第一个\subsection之前
        if body_parts:
            method_idx = min(2, len(body_parts) - 1)  # 第3章
            body_parts[method_idx] = body_parts[method_idx].replace(
                '\\subsection{', tikz_figure + '\n\\subsection{', 1
            )

    body = '\n\n'.join(body_parts)

    # 清理 Abstract 中的 Markdown 残留
    abstract_clean = _clean_abstract(abstract)
    keywords_clean = _clean_keywords(keywords)

    # 清理 Title 中的特殊字符
    title_clean = PAPER_TITLE.replace('&', '\\&').replace('%', '\\%').replace('#', '\\#')

    # 生成 author 格式（IEEE 标准）
    author_clean = authors.replace('&', '\\&')
    author_short = re.sub(r'[,{].*', '', authors.split(',')[0]).strip()
    title_short = title_clean[:50].rstrip()

    # 填充模板
    latex_paper = template
    latex_paper = latex_paper.replace('TITLE_PLACEHOLDER', title_clean)
    latex_paper = latex_paper.replace('AUTHOR_PLACEHOLDER', author_clean)
    latex_paper = latex_paper.replace('AUTHOR_SHORT_PLACEHOLDER', author_short)
    latex_paper = latex_paper.replace('TITLE_SHORT_PLACEHOLDER', title_short)
    latex_paper = latex_paper.replace('DATE_PLACEHOLDER', 'May 2026')
    latex_paper = latex_paper.replace('ABSTRACT_PLACEHOLDER', abstract_clean)
    latex_paper = latex_paper.replace('KEYWORDS_PLACEHOLDER', keywords_clean)
    latex_paper = latex_paper.replace('BODY_PLACEHOLDER', body)

    # ── 约束引擎：转换后立即检查 + 修复 ──
    try:
        from tools.latex_constraint_checker import run_constraint_check
        template_name = LATEX_TEMPLATE if LATEX_TEMPLATE in LATEX_TEMPLATES else "ieee_trans"
        constraint_result = run_constraint_check(
            latex_paper, template_type=template_name, auto_fix=True
        )
        if constraint_result.get("fixed_content"):
            latex_paper = constraint_result["fixed_content"]
        if not constraint_result.get("all_passed", True):
            logger.warning(
                f"[latex_converter] 约束检查: "
                f"{constraint_result['critical_count']} critical, "
                f"{constraint_result['warning_count']} warnings"
            )
        else:
            logger.info("[latex_converter] 约束检查全部通过")
    except Exception as e:
        logger.warning(f"[latex_converter] 约束检查失败（不阻塞）: {e}")

    return latex_paper


def _clean_abstract(abstract: str) -> str:
    """清理 Abstract 中的 Markdown 和标签残留"""
    text = abstract
    # 移除 ## Abstract 标题
    text = re.sub(r'^#{1,3}\s*Abstract\s*', '', text, flags=re.MULTILINE)
    # 移除 **Keywords:** 及之后的内容
    text = re.sub(r'\*\*Keywords?:\*\*.*$', '', text, flags=re.MULTILINE)
    # 移除 Markdown 格式
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # 移除 <formula> 标记
    text = re.sub(r'</?formula>', '', text)
    text = re.sub(r'</?citation>', '', text)
    
    # v9.2: 移除硬编码 AI 词汇替换
    # 现在由学术风格检查器（硬约束）和风格指南（柔性引导）处理
    
    return text.strip()


def _clean_keywords(keywords: str) -> str:
    """清理 Keywords"""
    text = keywords
    text = re.sub(r'\*\*Keywords?:\*\*\s*', '', text)
    text = re.sub(r'^Keywords?:\s*', '', text, flags=re.IGNORECASE)
    return text.strip()


def _fix_unpaired_environments(text: str) -> str:
    """
    修复未配对的 equation/align 环境
    确保 \begin{equation} 有对应的 \end{equation}
    """
    envs_to_check = ['equation', 'align', 'table', 'figure', 'abstract', 'IEEEkeywords']
    for env in envs_to_check:
        begins = len(re.findall(f'\\\\begin\\{{{env}\\}}', text))
        ends = len(re.findall(f'\\\\end\\{{{env}\\}}', text))
        if begins > ends:
            # 在 \end{document} 之前补上缺失的 \end
            diff = begins - ends
            for _ in range(diff):
                text += f'\n\\end{{{env}}}'
            logger.warning(f"[latex_converter] 修复未配对 {env}: 补了 {diff} 个 \\end{{{env}}}")
        elif ends > begins:
            # 多余的 \end，在第一个多余的之前补 \begin
            diff = ends - begins
            text = f'\\begin{{{env}}}\n' * diff + text
            logger.warning(f"[latex_converter] 修复未配对 {env}: 补了 {diff} 个 \\begin{{{env}}}")
    return text


def run_latex_converter(chapters: List[str], tikz_code: str = "",
                       abstract: str = "", keywords: str = "",
                       authors: str = "Anonymous") -> str:
    """主入口：转换为LaTeX论文"""
    try:
        os.makedirs(f"{OUTPUT_DIR}/latex", exist_ok=True)
    except OSError as e:
        logger.error(f"创建LaTeX输出目录失败: {e}")
        raise

    logger.info("[latex_converter] 转换各章节为LaTeX...")
    try:
        latex_paper = assemble_latex_paper(chapters, tikz_code, abstract, keywords, authors)
    except Exception as e:
        logger.error(f"LaTeX论文组装失败: {e}")
        raise

    # 保存主文件
    try:
        with open(f"{OUTPUT_DIR}/latex/main.tex", 'w', encoding='utf-8') as f:
            f.write(latex_paper)
    except IOError as e:
        logger.error(f"保存 main.tex 失败: {e}")

    # 生成空的references.bib（后续由BibTeX builder填充）
    bib_path = f"{OUTPUT_DIR}/latex/references.bib"
    if not os.path.exists(bib_path):
        try:
            with open(bib_path, 'w', encoding='utf-8') as f:
                f.write("% References will be populated by the BibTeX builder\n")
        except IOError as e:
            logger.error(f"保存 references.bib 失败: {e}")

    # 同时保存各章节的独立LaTeX文件
    for i, chapter in enumerate(chapters, 1):
        if not chapter or not chapter.strip():
            continue
        try:
            chapter_latex = markdown_to_latex(chapter)
            with open(f"{OUTPUT_DIR}/latex/chapter{i}.tex", 'w', encoding='utf-8') as f:
                f.write(chapter_latex)
        except Exception as e:
            logger.error(f"保存 chapter{i}.tex 失败: {e}")

    logger.info(f"[latex_converter] LaTeX论文已保存至 {OUTPUT_DIR}/latex/main.tex")

    return latex_paper


if __name__ == "__main__":
    import glob
    chapters = []
    tikz_code = ""

    for i in range(1, 6):
        files = glob.glob(f"{OUTPUT_DIR}/chapter{i}/chapter{i}_*.md")
        for f in sorted(files):
            with open(f, 'r', encoding='utf-8') as fh:
                chapters.append(fh.read())

    tikz_path = f"{OUTPUT_DIR}/chapter3/architecture_figure.tex"
    if os.path.exists(tikz_path):
        with open(tikz_path, 'r', encoding='utf-8') as f:
            tikz_code = f.read()

    if chapters:
        run_latex_converter(chapters, tikz_code)
