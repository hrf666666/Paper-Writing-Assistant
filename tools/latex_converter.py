# -*- coding: utf-8 -*-
"""
Tool: LaTeX转换器
将各章节Markdown内容转换为完整的LaTeX论文代码
"""

import os
import json
import re
from pathlib import Path

from config.project_config import (
    PAPER_TITLE, OUTPUT_DIR, LATEX_TEMPLATE, ARTICLE_TYPE, get_article_type_info
)


# LaTeX模板
LATEX_TEMPLATES = {
    "ieee_trans": r"""\documentclass[journal]{IEEEtran}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{algorithmic}
\usepackage{algorithm}
\usepackage{graphicx}
\usepackage{textcomp}
\usepackage{xcolor}
\usepackage{tikz}
\usetikzlibrary{positioning, arrows.meta, shapes.geometric, calc, fit}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{hyperref}
\usepackage{cite}

\newcommand{\texTitle}{TITLE_PLACEHOLDER}
\newcommand{\texAuthor}{AUTHOR_PLACEHOLDER}

\title{\texTitle}
\author{\texAuthor}

\begin{document}
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

\title{TITLE_PLACEHOLDER}
\author{AUTHOR_PLACEHOLDER}

\begin{document}
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


def markdown_to_latex(md_text):
    """将Markdown格式文本转换为LaTeX格式"""
    
    latex = md_text
    
    # 处理章节标题
    latex = re.sub(r'^# (.+)$', r'\\section{\1}', latex, flags=re.MULTILINE)
    latex = re.sub(r'^## (.+)$', r'\\subsection{\1}', latex, flags=re.MULTILINE)
    latex = re.sub(r'^### (.+)$', r'\\subsubsection{\1}', latex, flags=re.MULTILINE)
    
    # 处理加粗和斜体
    latex = re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', latex)
    latex = re.sub(r'\*(.+?)\*', r'\\textit{\1}', latex)
    
    # 处理<citation>标记 → \cite{}
    def replace_citation(match):
        try:
            import ast
            keywords = ast.literal_eval(match.group(1))
            # 简单处理：用关键词生成cite key
            cite_key = re.sub(r'[^a-zA-Z0-9]', '', "_".join(keywords[0] if isinstance(keywords[0], list) else keywords)[:30])
            return f'\\cite{{{cite_key}}}'
        except Exception:
            return f'\\cite{{?}}'
    
    latex = re.sub(r'<citation>(.*?)</citation>', replace_citation, latex, flags=re.DOTALL)
    
    # 处理<formula>标记 → \( \) 或 \[ \]
    def replace_formula(match):
        formula = match.group(1).strip()
        # 判断是行内公式还是行间公式
        if '\n' in formula or len(formula) > 80 or '\\' in formula:
            return f'\\[\n{formula}\n\\]'
        else:
            return f'\\({formula}\\)'
    
    latex = re.sub(r'<formula>(.*?)</formula>', replace_formula, latex, flags=re.DOTALL)
    
    # 处理Markdown表格 → LaTeX表格
    def replace_table(match):
        table_text = match.group(0)
        lines = table_text.strip().split('\n')
        if len(lines) < 3:
            return table_text
        
        # 解析表头
        header = [cell.strip() for cell in lines[0].split('|') if cell.strip()]
        # 跳过分隔行
        data_lines = []
        for line in lines[2:]:
            row = [cell.strip() for cell in line.split('|') if cell.strip()]
            if row:
                data_lines.append(row)
        
        if not header:
            return table_text
        
        col_count = len(header)
        col_spec = 'l' * col_count
        
        latex_table = f'\\begin{{table}}[htbp]\n\\centering\n\\caption{{TABLE_CAPTION}}\n'
        latex_table += f'\\begin{{tabular}}{{{col_spec}}}\n\\toprule\n'
        latex_table += ' & '.join(header) + ' \\\\\n\\midrule\n'
        
        for row in data_lines[:col_count]:
            latex_table += ' & '.join(row[:col_count]) + ' \\\\\n'
        
        latex_table += '\\bottomrule\n\\end{tabular}\n\\end{table}'
        return latex_table
    
    # 匹配Markdown表格
    latex = re.sub(r'(\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|\n?)+)', replace_table, latex, flags=re.MULTILINE)
    
    # 处理列表
    latex = re.sub(r'^- (.+)$', r'\\item \1', latex, flags=re.MULTILINE)
    # 包裹在itemize中（简单处理）
    
    # 处理代码块
    latex = re.sub(r'```(\w+)?\n(.*?)```', r'\\begin{verbatim}\n\2\n\\end{verbatim}', latex, flags=re.DOTALL)
    
    # 处理特殊字符（但不处理 \cite{} 和 \textbf{} 等已 LaTeX 化的内容）
    # 先保护 LaTeX 命令参数中的内容
    protected_parts = []
    def protect_latex(match):
        protected_parts.append(match.group(0))
        return f"__PROTECTED_{len(protected_parts) - 1}__"
    
    # 保护 \cite{...}, \textbf{...}, \textit{...}, \label{...}, \ref{...} 等命令
    latex = re.sub(r'\\(?:cite|textbf|textit|label|ref|section|subsection)\{[^}]*\}', protect_latex, latex)
    # 保护 \begin{...} \end{...}
    latex = re.sub(r'\\(?:begin|end)\{[^}]*\}', protect_latex, latex)
    
    # 处理特殊字符
    latex = latex.replace('&', '\\&')
    latex = latex.replace('%', '\\%')
    latex = latex.replace('#', '\\#')
    # 注意：不全局替换 _ ，因为 LaTeX 中 _ 在数学环境外才需要转义
    # 而 cite key 中通常包含 _
    
    # 恢复保护的内容
    for i, part in enumerate(protected_parts):
        latex = latex.replace(f"__PROTECTED_{i}__", part)
    
    return latex


def assemble_latex_paper(chapters, tikz_code="", abstract="", keywords="", authors=""):
    """将各章节组装为完整的LaTeX论文"""
    
    article_info = get_article_type_info()
    template_name = LATEX_TEMPLATE if LATEX_TEMPLATE in LATEX_TEMPLATES else "ieee_trans"
    template = LATEX_TEMPLATES[template_name]
    
    # 转换各章节
    body_parts = []
    for chapter in chapters:
        latex_chapter = markdown_to_latex(chapter)
        body_parts.append(latex_chapter)
    
    # 如果有TikZ架构图代码，插入到Methodology章节
    if tikz_code:
        tikz_figure = f"""
\\begin{{figure}}[t]
\\centering
{tikz_code}
\\caption{{Overall architecture of the proposed method.}}
\\label{{fig:architecture}}
\\end{{figure}}
"""
        # 插入到第一个\subsection之前
        if body_parts:
            method_idx = min(2, len(body_parts) - 1)  # 第3章
            body_parts[method_idx] = body_parts[method_idx].replace(
                '\\subsection{', tikz_figure + '\n\\subsection{', 1
            )
    
    body = '\n\n'.join(body_parts)
    
    # 填充模板
    latex_paper = template
    latex_paper = latex_paper.replace('TITLE_PLACEHOLDER', PAPER_TITLE)
    latex_paper = latex_paper.replace('AUTHOR_PLACEHOLDER', authors)
    latex_paper = latex_paper.replace('ABSTRACT_PLACEHOLDER', abstract)
    latex_paper = latex_paper.replace('KEYWORDS_PLACEHOLDER', keywords)
    latex_paper = latex_paper.replace('BODY_PLACEHOLDER', body)
    
    return latex_paper


def run_latex_converter(chapters, tikz_code="", abstract="", keywords="", authors="Anonymous"):
    """主入口：转换为LaTeX论文"""
    os.makedirs(f"{OUTPUT_DIR}/latex", exist_ok=True)
    
    print("[latex_converter] 转换各章节为LaTeX...")
    latex_paper = assemble_latex_paper(chapters, tikz_code, abstract, keywords, authors)
    
    # 保存主文件
    with open(f"{OUTPUT_DIR}/latex/main.tex", 'w', encoding='utf-8') as f:
        f.write(latex_paper)
    
    # 生成空的references.bib
    bib_content = "% References will be populated by the reference checker\n"
    with open(f"{OUTPUT_DIR}/latex/references.bib", 'w', encoding='utf-8') as f:
        f.write(bib_content)
    
    # 同时保存各章节的独立LaTeX文件
    for i, chapter in enumerate(chapters, 1):
        chapter_latex = markdown_to_latex(chapter)
        with open(f"{OUTPUT_DIR}/latex/chapter{i}.tex", 'w', encoding='utf-8') as f:
            f.write(chapter_latex)
    
    print(f"[latex_converter] LaTeX论文已保存至 {OUTPUT_DIR}/latex/main.tex")
    
    return latex_paper


if __name__ == "__main__":
    # 读取各章节并转换
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
