# -*- coding: utf-8 -*-
"""
Tool: LaTeX转换器 v12.0 — LLM 直出 + 审查修复循环

架构变更（v12.0）：
1. 删除 500 行正则 markdown_to_latex（bug 工厂）
2. Chapter prompt 直接输出 LaTeX（不再走 Markdown 中间格式）
3. LLM 审查+修复循环替代正则转换
4. 编译错误反馈 → LLM 自愈（最多 2 轮）

流程：
  Chapter Prompt → LLM 输出 LaTeX → 审查(一致性/格式) → 编译 → 反馈修复
"""

import os
import re
import logging
from typing import List, Tuple

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


def _get_tool_api():
    """延迟获取 API 客户端"""
    try:
        from tools.base_tool import get_tool_api
        return get_tool_api()
    except Exception:
        from agent.api_client import get_api_client
        return get_api_client()


# ═══════════════════════════════════════════════════════════════
# LLM LaTeX 审查 + 修复
# ═══════════════════════════════════════════════════════════════

def _count_sections(latex: str) -> int:
    """统计 \\section / \\subsection 数量，用于结构完整性检查"""
    return len(re.findall(r'\\section\{|\\subsection\{', latex))


def _safe_llm_replace(original: str, candidate: str, label: str,
                      min_ratio: float = 0.5) -> str:
    """
    安全替换守卫：防止 LLM 返回截断/压缩内容覆盖原始内容。

    Args:
        original: 原始 LaTeX 内容
        candidate: LLM 返回的候选内容
        label: 日志标签（如 "章节1审查"）
        min_ratio: 最低长度比率，低于此值拒绝替换

    Returns:
        安全的内容（candidate 或 original）
    """
    if not candidate or len(candidate.strip()) < 50:
        logger.info(f"[latex_converter] {label}: LLM返回过短(<50)，保留原文")
        return original

    orig_len = len(original)
    cand_len = len(candidate)

    # 长度守卫：如果候选内容 < 原始的 min_ratio，拒绝替换
    if orig_len > 200 and cand_len < orig_len * min_ratio:
        logger.warning(
            f"[latex_converter] {label}: 长度守卫触发 — "
            f"候选 {cand_len} < 原始 {orig_len} 的 {min_ratio:.0%}，保留原文"
        )
        return original

    # 结构守卫：section/subsection 数量不应大幅减少
    orig_secs = _count_sections(original)
    cand_secs = _count_sections(candidate)
    if orig_secs > 0 and cand_secs < orig_secs - 1:
        logger.warning(
            f"[latex_converter] {label}: 结构守卫触发 — "
            f"section/subsection 从 {orig_secs} 减少到 {cand_secs}，保留原文"
        )
        return original

    return candidate


def _review_latex(latex_content: str, chapter_num: int) -> Tuple[str, List[str]]:
    """
    LLM 审查 LaTeX 内容，返回 (修复后内容, 问题列表)。
    v12.1: 添加长度/结构守卫，防止 LLM 截断/压缩内容。
    """
    api = _get_tool_api()
    if not api:
        return latex_content, []

    prompt = f"""你是一名 IEEE Transactions (IEEEtran 格式) 的 LaTeX 审查专家。
请审查以下 LaTeX 章节代码，只修复格式问题。

**CRITICAL: 保持所有原始内容不变！不要删除、总结或压缩任何文字段落。只修复格式错误。**

**检查清单**:
1. 花括号 {{ }} 是否正确配对
2. 每个 \\begin{{X}} 是否有对应的 \\end{{X}}（equation, align, table, figure, itemize 等）
3. 是否有 Markdown 残留（##, **, - 列表项不在 itemize 中）
4. 表格使用 \\toprule/\\midrule/\\bottomrule（不要用 \\hline）
5. 表格用 \\resizebox{{\\columnwidth}}{{!}}{{}} 或 \\resizebox{{\\textwidth}}{{!}}{{}} 包裹
6. 行间公式使用 \\begin{{equation}} 或 \\begin{{align}}（不要用 $$...$$）
7. 无中文字符
8. 所有 <citation> 标记保持不变（不要删除或修改）
9. 文本中使用 \\&（不要在 tabular 外使用裸 &）
10. 不重复输出已有的 \\section/\\subsection 标题

**输出完整的修正后 LaTeX 代码，包含所有原始文字内容。如果没有格式问题，原样输出。**

待审查的 LaTeX:
```
{latex_content}
```"""

    try:
        result = api.call_generation(prompt)
        if result:
            # 清理 markdown 包裹
            result = result.strip()
            if result.startswith("```"):
                lines = result.split("\n")
                result = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            # v12.1: 安全替换守卫（50% 长度阈值 + 结构完整性检查）
            safe_result = _safe_llm_replace(
                latex_content, result.strip(),
                f"章节{chapter_num}审查", min_ratio=0.5
            )
            # 检测修复了哪些问题
            issues = []
            if safe_result != latex_content:
                issues.append(f"章节{chapter_num}: LLM审查修复了格式问题")
            return safe_result, issues
    except Exception as e:
        logger.warning(f"[latex_converter] 章节 {chapter_num} LLM审查失败: {e}")

    return latex_content, []


def _fix_compile_errors(latex_content: str, errors: str) -> str:
    """
    将编译错误反馈给 LLM，让其修复
    """
    api = _get_tool_api()
    if not api:
        return latex_content

    prompt = f"""The following LaTeX code has compilation errors.
Fix ALL errors. Output ONLY the corrected LaTeX code.

**COMPILATION ERRORS**:
{errors[:2000]}

**LaTeX code**:
```
{latex_content[:16000]}
```

Fix the errors and output the corrected LaTeX:"""

    try:
        result = api.call_generation(prompt)
        if result:
            result = result.strip()
            if result.startswith("```"):
                lines = result.split("\n")
                result = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            # v12.1: 安全替换守卫（编译修复允许更激进，30% 阈值）
            safe_result = _safe_llm_replace(
                latex_content, result.strip(),
                "编译修复", min_ratio=0.3
            )
            return safe_result
    except Exception as e:
        logger.warning(f"[latex_converter] 编译修复失败: {e}")

    return latex_content


# ═══════════════════════════════════════════════════════════════
# 章节组装
# ═══════════════════════════════════════════════════════════════

def _deduplicate_sections(body_parts: List[str]) -> List[str]:
    """跨章节去重：检测重复的 \\section 标题"""
    seen_sections = set()
    result = []
    for part in body_parts:
        lines = part.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            sec_match = re.match(r'^\\section\{(.+?)\}', stripped)
            if sec_match:
                title = sec_match.group(1).lower()
                if title in seen_sections:
                    logger.info(f"[latex_converter] 移除重复section: {sec_match.group(1)}")
                    continue
                seen_sections.add(title)
            cleaned_lines.append(line)
        if cleaned_lines:
            result.append('\n'.join(cleaned_lines))
    return result


def _minimal_cleanup(latex: str) -> str:
    """
    最小化清理 — 只做正则不可能出错的事
    
    注意：<citation> 标记不在此时清理！
    它们由 Phase 7.8 (BibTeX 引用替换) 处理，替换为 \\cite{key}。
    """
    # [!] 不要清理 <citation> 标记！Phase 7.8 负责替换它们为 \cite{key}
    # 清理 [?] 引用占位符
    latex = re.sub(r'\[\?\]', '', latex)
    # 清理空 section
    latex = re.sub(r'\\section\{\s*\}', '', latex)
    latex = re.sub(r'\\subsection\{\s*\}', '', latex)
    # 清理残余 Markdown 标题（以防 prompt 指令被忽略）
    latex = re.sub(r'^#{1,6}\s+', '', latex, flags=re.MULTILINE)
    # v11.2: 清理中文字符（不应出现在英文论文 LaTeX 中）
    latex = re.sub(r'[\u4e00-\u9fff]+', '', latex)
    return latex


def assemble_latex_paper(chapters: List[str], tikz_code: str = "",
                         abstract: str = "", keywords: str = "",
                         authors: str = None) -> str:
    """
    组装 LaTeX 论文 — v12.0 LLM 直出版

    chapters 列表中的内容已经是 LaTeX 格式（由 chapter prompt 直接生成）。
    不再走 Markdown → LaTeX 正则转换。
    """
    # 使用配置中的作者信息
    if authors is None or authors == "Anonymous":
        authors = PAPER_AUTHORS

    article_info = get_article_type_info()
    template_name = LATEX_TEMPLATE if LATEX_TEMPLATE in LATEX_TEMPLATES else "ieee_trans"
    template = LATEX_TEMPLATES[template_name]

    # ── 处理各章节（已经是 LaTeX） ──
    body_parts = []
    for i, chapter in enumerate(chapters):
        if not chapter or not chapter.strip():
            continue

        # v12.0: chapter prompt 直接输出 LaTeX，只需最小清理
        latex_chapter = _minimal_cleanup(chapter.strip())

        # LLM 审查修复（1 轮）
        latex_chapter, issues = _review_latex(latex_chapter, i + 1)
        if issues:
            logger.info(f"[latex_converter] 章节 {i+1} 审查修复了 {len(issues)} 个问题")

        body_parts.append(latex_chapter)

    # 跨章节去重
    body_parts = _deduplicate_sections(body_parts)

    # 插入 TikZ 架构图
    if tikz_code:
        tikz_figure = f"""
\\begin{{figure*}}[!t]
\\centering
{tikz_code}
\\caption{{Overall architecture of the proposed method.}}
\\label{{fig:architecture}}
\\end{{figure*}}
"""
        if body_parts:
            method_idx = min(2, len(body_parts) - 1)
            body_parts[method_idx] = body_parts[method_idx].replace(
                '\\subsection{', tikz_figure + '\n\\subsection{', 1
            )

    body = '\n\n'.join(body_parts)

    # 清理 Abstract / Keywords
    abstract_clean = _clean_abstract(abstract)
    keywords_clean = _clean_keywords(keywords)

    # 填充模板
    title_clean = PAPER_TITLE.replace('&', '\\&').replace('%', '\\%').replace('#', '\\#')
    author_clean = authors.replace('&', '\\&')
    author_short = re.sub(r'[,{].*', '', authors.split(',')[0]).strip()
    title_short = title_clean[:50].rstrip()

    latex_paper = template
    latex_paper = latex_paper.replace('TITLE_PLACEHOLDER', title_clean)
    latex_paper = latex_paper.replace('AUTHOR_PLACEHOLDER', author_clean)
    latex_paper = latex_paper.replace('AUTHOR_SHORT_PLACEHOLDER', author_short)
    latex_paper = latex_paper.replace('TITLE_SHORT_PLACEHOLDER', title_short)
    latex_paper = latex_paper.replace('DATE_PLACEHOLDER', 'May 2026')
    latex_paper = latex_paper.replace('ABSTRACT_PLACEHOLDER', abstract_clean)
    latex_paper = latex_paper.replace('KEYWORDS_PLACEHOLDER', keywords_clean)
    latex_paper = latex_paper.replace('BODY_PLACEHOLDER', body)

    # ── 后处理修复链 ──
    try:
        from tools.latex_direct_generator import (
            _fix_textwidth_confusion, _ensure_table_resizebox,
            _ensure_tikz_fits, _validate_float_sizing,
            _fix_long_equations,
        )
        latex_paper = _fix_textwidth_confusion(latex_paper)
        latex_paper = _ensure_table_resizebox(latex_paper)
        latex_paper = _ensure_tikz_fits(latex_paper)
        latex_paper = _validate_float_sizing(latex_paper)
        latex_paper = _fix_long_equations(latex_paper)
        logger.info("[latex_converter] 后处理修复链完成 (5 步)")
    except Exception as e:
        logger.warning(f"[latex_converter] 后处理修复链失败（不阻塞）: {e}")

    return latex_paper


def _clean_abstract(abstract: str) -> str:
    """清理 Abstract"""
    text = abstract
    text = re.sub(r'^#{1,3}\s*Abstract\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*Keywords?:\*\*.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'</?formula>', '', text)
    # [!] 不要清理 <citation> 标记，Phase 7.8 负责替换
    return text.strip()


def _clean_keywords(keywords: str) -> str:
    """清理 Keywords"""
    text = keywords
    text = re.sub(r'\*\*Keywords?:\*\*\s*', '', text)
    text = re.sub(r'^Keywords?:\s*', '', text, flags=re.IGNORECASE)
    return text.strip()


def run_latex_converter(chapters: List[str], tikz_code: str = "",
                       abstract: str = "", keywords: str = "",
                       authors: str = "Anonymous") -> str:
    """主入口：组装 LaTeX 论文"""
    try:
        os.makedirs(f"{OUTPUT_DIR}/latex", exist_ok=True)
    except OSError as e:
        logger.error(f"创建LaTeX输出目录失败: {e}")
        raise

    logger.info("[latex_converter] 组装LaTeX论文（LLM直出模式）...")
    try:
        latex_paper = assemble_latex_paper(chapters, tikz_code, abstract, keywords, authors)
    except Exception as e:
        logger.error(f"LaTeX论文组装失败: {e}")
        raise

    # 保存
    try:
        with open(f"{OUTPUT_DIR}/latex/main.tex", 'w', encoding='utf-8') as f:
            f.write(latex_paper)
    except IOError as e:
        logger.error(f"保存 main.tex 失败: {e}")

    # 空 references.bib（后续由 BibTeX builder 填充）
    bib_path = f"{OUTPUT_DIR}/latex/references.bib"
    if not os.path.exists(bib_path):
        try:
            with open(bib_path, 'w', encoding='utf-8') as f:
                f.write("% References will be populated by the BibTeX builder\n")
        except IOError as e:
            logger.error(f"保存 references.bib 失败: {e}")

    logger.info(f"[latex_converter] LaTeX论文已保存至 {OUTPUT_DIR}/latex/main.tex")
    return latex_paper


if __name__ == "__main__":
    import glob
    chapters = []

    for i in range(1, 6):
        files = glob.glob(f"{OUTPUT_DIR}/chapter{i}/chapter{i}_*.md")
        for f in sorted(files):
            with open(f, 'r', encoding='utf-8') as fh:
                chapters.append(fh.read())

    tikz_path = f"{OUTPUT_DIR}/chapter3/architecture_figure.tex"
    tikz_code = ""
    if os.path.exists(tikz_path):
        with open(tikz_path, 'r', encoding='utf-8') as f:
            tikz_code = f.read()

    if chapters:
        run_latex_converter(chapters, tikz_code)
