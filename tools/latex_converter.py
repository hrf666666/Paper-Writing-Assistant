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
from typing import List, Optional, Tuple

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

    # v15.2: 公式守卫 — equation/align 数量不应大幅减少
    orig_eqs = len(re.findall(r'\\begin\{equation\}|\\begin\{align\}', original))
    cand_eqs = len(re.findall(r'\\begin\{equation\}|\\begin\{align\}', candidate))
    if orig_eqs >= 3 and cand_eqs < orig_eqs * 0.5:
        logger.warning(
            f"[latex_converter] {label}: 公式守卫触发 — "
            f"equation/align 从 {orig_eqs} 减少到 {cand_eqs}，保留原文"
        )
        return original

    # v15.2: cite 守卫 — 引用数量不应大幅减少
    orig_cites = len(re.findall(r'\\cite\{|<citation', original))
    cand_cites = len(re.findall(r'\\cite\{|<citation', candidate))
    if orig_cites >= 3 and cand_cites < orig_cites * 0.5:
        logger.warning(
            f"[latex_converter] {label}: 引用守卫触发 — "
            f"cite 从 {orig_cites} 减少到 {cand_cites}，保留原文"
        )
        return original

    return candidate


def _lint_latex(latex: str) -> str:
    """
    v15.2: 纯正则清理 — 只删除明确不该存在的东西，不做任何风格转换。
    替代 _review_latex 的格式修复职责，零 LLM 调用，零幻觉风险。
    """
    # Markdown 残留 (LLM 偶尔泄漏)
    latex = re.sub(r'^#{1,6}\s+', '', latex, flags=re.MULTILINE)
    latex = re.sub(r'\*\*(.+?)\*\*', r'\1', latex)
    latex = re.sub(r'(?<!\S)\*(.+?)\*(?!\S)', r'\1', latex)  # 不碰 $a*b$
    # [?] 引用占位符
    latex = re.sub(r'\[\?\]', '', latex)
    # multline → equation+split (IEEEtran 兼容, 复用已有函数)
    latex = _replace_multline(latex)
    return latex


def _find_pdflatex_binary() -> Optional[str]:
    """查找 pdflatex 可执行文件路径"""
    import shutil as _shutil
    found = _shutil.which("pdflatex")
    if found:
        return found
    for candidate in [
        "/usr/local/texlive/2026/bin/x86_64-linux/pdflatex",
        "/usr/local/texlive/2025/bin/x86_64-linux/pdflatex",
        "/usr/local/texlive/2024/bin/x86_64-linux/pdflatex",
        "/usr/bin/pdflatex",
    ]:
        if os.path.isfile(candidate):
            return candidate
    return None


def _extract_errors_from_log(tmp_dir: str, result) -> str:
    """从 pdflatex 运行结果提取错误信息。优先读 .log 文件。"""
    log_path = os.path.join(tmp_dir, "verify.log")
    log_content = ""
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            log_content = f.read()
    if not log_content:
        log_content = (result.stdout or "") + "\n" + (result.stderr or "")
    # 提取以 ! 开头的错误行 + 后续 3 行上下文
    errors = []
    lines = log_content.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("!"):
            context = lines[i:i + 4]
            errors.append("\n".join(context))
    return "\n\n".join(errors[:10]) if errors else log_content[-1500:]


# IEEEtran standalone preamble (与 main.tex 同款)
_STANDALONE_PREAMBLE = (
    "\\documentclass[lettersize,journal]{IEEEtran}\n"
    "\\usepackage{amsmath,amssymb,amsfonts}\n"
    "\\usepackage{algorithmic}\n"
    "\\usepackage{algorithm}\n"
    "\\usepackage{array}\n"
    "\\usepackage[caption=false,font=normalsize,labelfont=sf,textfont=sf]{subfig}\n"
    "\\usepackage{textcomp}\n"
    "\\usepackage{stfloats}\n"
    "\\usepackage{url}\n"
    "\\usepackage{graphicx}\n"
    "\\usepackage{xcolor}\n"
    "\\usepackage{tikz}\n"
    "\\usetikzlibrary{positioning, arrows.meta, shapes.geometric, calc, fit}\n"
    "\\usepackage{booktabs}\n"
    "\\usepackage{multirow}\n"
    "\\usepackage{hyperref}\n"
    "\\usepackage{cite}\n"
    "\\hyphenation{op-tical net-works semi-conduc-tor}\n"
    "\\begin{document}\n"
)


def _fix_chapter_latex(chapter_latex: str, error_log: str,
                       chapter_num: int) -> str:
    """
    v15.2: 基于编译器报错日志修复单章 LaTeX。
    与 _fix_compile_errors 的区别: 输入是单章(不截断), 错误来自 standalone dry-compile。
    """
    api = _get_tool_api()
    if not api:
        return chapter_latex

    prompt = f"""Fix the LaTeX compilation errors in this chapter section.

**COMPILATION ERRORS** (from pdflatex):
{error_log[:3000]}

**RULES**:
1. Fix ONLY the errors listed above
2. Preserve ALL text content, equations, tables, and \\cite{{}} commands
3. Do NOT delete paragraphs, sections, or equations
4. If a table has structural errors, fix the structure — don't delete the table
5. If an equation has syntax errors, fix the syntax — don't delete the equation
6. Output the COMPLETE corrected chapter LaTeX (same content, errors fixed)

**Chapter LaTeX**:
```latex
{chapter_latex}
```

Output ONLY the corrected LaTeX (no markdown fences, no explanations):"""

    try:
        result = api.call_generation(prompt)
        if not result or len(result.strip()) < 50:
            return chapter_latex

        result = result.strip()
        if result.startswith("```"):
            lines = result.split("\n")
            result = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        # 安全守卫: 修复后不能比原文短太多
        orig_len = len(chapter_latex)
        fixed_len = len(result)
        if orig_len > 500 and fixed_len < orig_len * 0.5:
            logger.warning(
                f"[Chapter {chapter_num}] 修复后长度 {fixed_len} < 原文 {orig_len} 的 50%, 拒绝替换"
            )
            return chapter_latex

        # 公式守卫
        orig_eqs = len(re.findall(r'\\begin\{equation\}|\\begin\{align\}', chapter_latex))
        fixed_eqs = len(re.findall(r'\\begin\{equation\}|\\begin\{align\}', result))
        if orig_eqs >= 3 and fixed_eqs < orig_eqs * 0.5:
            logger.warning(
                f"[Chapter {chapter_num}] 公式数 {orig_eqs}→{fixed_eqs}, 拒绝替换"
            )
            return chapter_latex

        # cite 守卫
        orig_cites = len(re.findall(r'\\cite\{', chapter_latex))
        fixed_cites = len(re.findall(r'\\cite\{', result))
        if orig_cites >= 3 and fixed_cites < orig_cites * 0.5:
            logger.warning(
                f"[Chapter {chapter_num}] cite 数 {orig_cites}→{fixed_cites}, 拒绝替换"
            )
            return chapter_latex

        return result

    except Exception as e:
        logger.warning(f"[Chapter {chapter_num}] LLM 修复失败: {e}")
        return chapter_latex


def _dry_compile_chapter(chapter_latex: str, chapter_num: int,
                         max_retries: int = 2) -> str:
    """
    v15.2: 逐章 standalone 编译验证 + LLM 自愈。
    策略与 tikz_generator._compile_verify_and_fix 一致:
    1. 包裹 standalone 文档 → pdflatex 编译
    2. 成功 → 返回原样
    3. 失败 → 解析错误 → 喂给 LLM 修复 → 重编译
    4. 最多 max_retries 轮，失败则返回原文
    """
    import subprocess
    import tempfile
    import shutil as _shutil

    pdflatex = _find_pdflatex_binary()
    if not pdflatex:
        logger.info(f"[Chapter {chapter_num}] pdflatex 不可用, 跳过 dry-compile")
        return chapter_latex

    tmp_dir = tempfile.mkdtemp(prefix=f"chapter{chapter_num}_")
    try:
        tex_path = os.path.join(tmp_dir, "verify.tex")

        def _write_and_compile(content: str):
            with open(tex_path, "w", encoding="utf-8") as f:
                f.write(_STANDALONE_PREAMBLE + content + "\n\\end{document}\n")
            r = subprocess.run(
                [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "verify.tex"],
                cwd=tmp_dir, capture_output=True, text=True, timeout=30,
            )
            pdf_path = os.path.join(tmp_dir, "verify.pdf")
            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 500:
                return True, ""
            return False, _extract_errors_from_log(tmp_dir, r)

        # 第一次编译
        success, error_log = _write_and_compile(chapter_latex)
        if success:
            logger.info(f"[Chapter {chapter_num}] dry-compile 通过")
            return chapter_latex

        logger.warning(
            f"[Chapter {chapter_num}] dry-compile 失败, 错误: {error_log[:200]}"
        )

        # LLM 修复循环
        current = chapter_latex
        for attempt in range(max_retries):
            logger.info(
                f"[Chapter {chapter_num}] LLM 修复 (attempt {attempt + 1}/{max_retries})"
            )
            fixed = _fix_chapter_latex(current, error_log, chapter_num)

            if fixed == current:
                logger.warning(f"[Chapter {chapter_num}] LLM 未做出修改, 停止重试")
                return current

            success, error_log = _write_and_compile(fixed)
            if success:
                logger.info(
                    f"[Chapter {chapter_num}] LLM 修复后编译通过 (attempt {attempt + 1})"
                )
                return fixed

            current = fixed

        logger.warning(
            f"[Chapter {chapter_num}] dry-compile 失败 ({max_retries} 轮后仍失败), 使用原文"
        )
        return chapter_latex

    except subprocess.TimeoutExpired:
        logger.warning(f"[Chapter {chapter_num}] dry-compile 超时, 使用原文")
        return chapter_latex
    except FileNotFoundError:
        logger.info(f"[Chapter {chapter_num}] pdflatex 不可用, 跳过")
        return chapter_latex
    except Exception as e:
        logger.warning(f"[Chapter {chapter_num}] dry-compile 异常: {e}")
        return chapter_latex
    finally:
        _shutil.rmtree(tmp_dir, ignore_errors=True)


def _fix_compile_errors(latex_content: str, errors: str) -> str:
    """
    全量编译修复 — 基于编译器报错日志修复整篇 LaTeX (兜底用)。
    """
    api = _get_tool_api()
    if not api:
        return latex_content

    prompt = f"""Fix the LaTeX compilation errors. Fix ONLY the errors listed below.

**COMPILATION ERRORS** (fix these specific issues only):
{errors[:2000]}

**RULES**:
1. Only modify lines that cause the errors
2. Preserve ALL text content, equations, tables, and citations
3. Do NOT delete paragraphs or sections to "fix" errors
4. If an error is in a table, fix the table structure — don't delete the table
5. If an error is in an equation, fix the syntax — don't delete the equation

**LaTeX code**:
```
{latex_content[:16000]}
```

Output ONLY the corrected LaTeX:"""

    try:
        result = api.call_generation(prompt)
        if result:
            result = result.strip()
            if result.startswith("```"):
                lines = result.split("\n")
                result = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
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

    # v14: 处理 section/subsection 标题中的中文字符
    # LLM 可能生成 \subsection{中文标题 (English Title)}
    # 策略：保留括号内英文，删除中文；无括号则删除整个中文串
    def _clean_section_title(m):
        cmd = m.group(1)   # \subsection
        full_title = m.group(2)
        # 如果包含括号内的英文，保留括号内部分
        paren_match = re.search(r'\(([^)]+)\)', full_title)
        if paren_match:
            return f'{cmd}{{{paren_match.group(1).strip()}}}'
        # 否则删除中文字符
        cleaned = re.sub(r'[\u4e00-\u9fff]+', '', full_title)
        cleaned = re.sub(r'[（）、，：；！？]+', '', cleaned).strip()
        return f'{cmd}{{{cleaned}}}' if cleaned else m.group(0)

    latex = re.sub(r'(\\(?:sub)?section)\{([^}]*[\u4e00-\u9fff][^}]*)\}', _clean_section_title, latex)

    # 清理正文中残留的中文字符（section 标题已单独处理）
    latex = re.sub(r'[\u4e00-\u9fff]+', '', latex)
    # v15.2: 清理中文剥离后留下的空括号和空 \text{}
    latex = re.sub(r'\(\s*\)', '', latex)
    latex = re.sub(r'\\text\{\s*\}', '', latex)
    return latex


def _replace_multline(latex_code: str) -> str:
    """
    兜底：将 LLM 生成的 \\begin{multline}...\\end{multline} 替换为 equation+split。
    multline 在 IEEEtran 中因空行问题频繁导致编译错误。
    """
    def _fix(m):
        body = m.group(1).strip()
        body = re.sub(r'\n\s*\n', '\n', body)
        lines = [l.strip() for l in body.split('\\\\') if l.strip()]
        if len(lines) <= 1:
            single = lines[0] if lines else body
            return f'\\begin{{equation}}\n{single}\n\\end{{equation}}'
        first = lines[0]
        rest = ' \\\\\n&\\quad '.join(lines[1:])
        return f'\\begin{{equation}}\n\\begin{{split}}\n{first} \\\\\n&\\quad {rest}\n\\end{{split}}\n\\end{{equation}}'

    result = re.sub(
        r'\\begin\{multline\}(.*?)\\end\{multline\}',
        _fix, latex_code, flags=re.DOTALL,
    )
    count = len(re.findall(r'\\begin\{multline\}', latex_code))
    if count:
        logger.info(f"[latex_converter] multline → equation+split: {count} 处")
    return result


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

        # v15.2: chapter prompt 直接输出 LaTeX，只需最小清理
        latex_chapter = _minimal_cleanup(chapter.strip())

        # v15.2: 纯正则清理 + 逐章编译验证（替代 _review_latex LLM 审查）
        latex_chapter = _lint_latex(latex_chapter)
        latex_chapter = _dry_compile_chapter(latex_chapter, i + 1)

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
        )
        latex_paper = _fix_textwidth_confusion(latex_paper)
        latex_paper = _ensure_table_resizebox(latex_paper)
        latex_paper = _ensure_tikz_fits(latex_paper)
        latex_paper = _validate_float_sizing(latex_paper)
        # _fix_long_equations 已移除：它对 A=B 单等式按 = 拆行，
        # 产生缺 & 对齐符的 split 块，导致 "split won't work here"
        # 和级联的 Missing $ / Bad math / \eqno 错误（净负作用）。
        # 公式溢出应由编译后的 _overflow_heal_loop（基于真实 Overfull 日志）处理。
        # 兜底：LLM 自行生成的 multline → equation+split（IEEEtran 安全）
        latex_paper = _replace_multline(latex_paper)
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
