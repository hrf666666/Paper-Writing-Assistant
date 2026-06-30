# -*- coding: utf-8 -*-
"""vertical_checkers — v16.3 纵向专项审查 agent（中央部委）。

分层治理架构第2层：跨章节贯穿的专项检查。每个 Checker 只审不改，
产 Finding（带 fix 建议）入 FindingBus。修复交 FixExecutor，验收交 Verifier。

解决 PDF 实际暴露的 4 类问题：
  - BibInspector:    references.bib 的 author 格式（全名 vs Last,First）
  - FormulaChecker:  公式超界（长公式无换行）
  - TableChecker:    表格 resizebox 强缩后字号过小
  - FigureInspector: 图尺寸/版式适配（横向流图塞不进分配宽度）

设计原则（治理架构）：
  - 只审不改：产出 Finding，不直接修文件
  - 边界清晰：每个 Checker 只管自己的专项
  - Finding 带修复建议：fix 字段告诉 FixExecutor 怎么改
"""
import os
import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def _make_finding(source: str, kind: str, severity, location_chapter: str,
                  target: str, evidence: str, fix_hint: str, op: str = "replace_text"):
    """构造 Finding（统一工厂）。

    Args:
        target: 定位锚（bib key / 公式编号 / fig_id）
        fix_hint: 给 FixExecutor 的人类可读修复提示
        op: FixAction.op（replace_text/replace_number/regenerate/rerender_figure）
    """
    from agent.core.finding import Finding, Severity, Location, FixAction
    sev = severity if isinstance(severity, Severity) else Severity(severity)
    return Finding(
        source=source,
        kind=kind,
        severity=sev,
        description=fix_hint,
        location=Location(chapter=location_chapter, raw=target[:80]),
        evidence=evidence[:200],
        fix=FixAction(op=op, target=target, hint=fix_hint),
    )


# ═══════════════════════════════════════════════════════════════
# BibInspector — 参考文献 author 格式检查
# ═══════════════════════════════════════════════════════════════

def inspect_bib(bib_path: str) -> List:
    """检查 references.bib 的 author 字段格式。

    问题：author={Ben Mildenhall, Pratul P. Srinivasan, ...} 用全名，
    IEEEtran 会把每个 token 拆首字母 → "M.T.J.T.B." 乱码。
    正确格式：author={Mildenhall, Ben and Srinivasan, Pratul P.}
    """
    findings = []
    if not os.path.exists(bib_path):
        return findings
    content = open(bib_path, "r", encoding="utf-8").read()
    # 匹配每个 bib 条目的 author 字段
    for m in re.finditer(r'@\w+\{([^,]+),.*?author\s*=\s*\{([^}]+)\}', content, re.DOTALL):
        key = m.group(1).strip()
        author_str = m.group(2)
        # 检查：正确格式应有 "Last, First" （含逗号在名字内），全名格式是 "First Last and ..."
        # 启发式：如果 author_str 含 " and " 但没有任何 "X, Y"（逗号在单词间），可能是全名
        names = [n.strip() for n in re.split(r'\s+and\s+', author_str) if n.strip()]
        has_comma_format = any(',' in n for n in names)
        if not has_comma_format and len(names) >= 2:
            # 全名格式 → 建议转 Last, First
            converted = []
            for n in names:
                parts = n.split()
                if len(parts) >= 2:
                    last = parts[-1]
                    first = ' '.join(parts[:-1])
                    converted.append(f"{last}, {first}")
                else:
                    converted.append(n)
            fix_str = " and ".join(converted)
            findings.append(_make_finding(
                source="bib_inspector", kind="author_format",
                severity="warning", location_chapter="references.bib",
                target=f"@{key}",
                evidence=f"author={{{author_str[:80]}}}",
                fix_hint=f'author={{{fix_str}}}',
            ))
    if findings:
        logger.info(f"[BibInspector] {len(findings)} 条 author 格式问题（全名→Last,First）")
    return findings


# ═══════════════════════════════════════════════════════════════
# FormulaChecker — 公式超界检查
# ═══════════════════════════════════════════════════════════════

# 公式行长度阈值（IEEE 单栏 ~8.8cm，约 80-100 字符的 LaTeX 源会超界）
_FORMULA_OVERFLOW_CHARS = 120

def inspect_formulas(tex_path: str) -> List:
    """检查公式是否可能超界（长公式无 split/multline 换行）。

    问题：长公式（>120字符）直接平铺，IEEE 单栏塞不下 → 超出右边界。
    """
    findings = []
    if not os.path.exists(tex_path):
        return findings
    content = open(tex_path, "r", encoding="utf-8").read()
    # 找所有 equation/align/gather 环境
    for m in re.finditer(
        r'\\begin\{(equation|align|gather|multline)\*?\}(.*?)\\end\{\1\*?\}',
        content, re.DOTALL
    ):
        env = m.group(1)
        body = m.group(2)
        # 找最长行
        lines = [l for l in body.split('\n') if l.strip()]
        if not lines:
            continue
        longest = max(lines, key=len)
        longest_len = len(longest.strip())
        has_split = any(x in body for x in (
            '\\begin{split}', '\\begin{aligned}', '\\\\', 'multline',
            '\\begin{cases}',
        ))
        if longest_len > _FORMULA_OVERFLOW_CHARS and not has_split:
            findings.append(_make_finding(
                source="formula_checker", kind="overflow",
                severity="warning", location_chapter="main.tex",
                target=f"\\begin{{{env}}} 最长行{longest_len}字",
                evidence=longest.strip()[:100],
                fix_hint=f"公式超{longest_len}字符，建议用 split/multline 换行，或拆成多个子公式",
            ))
    if findings:
        logger.info(f"[FormulaChecker] {len(findings)} 条公式超界（>{_FORMULA_OVERFLOW_CHARS}字符无换行）")
    return findings


# ═══════════════════════════════════════════════════════════════
# TableChecker — 表格可读性检查
# ═══════════════════════════════════════════════════════════════

def inspect_tables(tex_path: str) -> List:
    """检查表格 resizebox 强缩后是否字号过小。

    问题：\\resizebox{\\columnwidth}{!} 对多列表格强缩 → 字号过小不可读。
    """
    findings = []
    if not os.path.exists(tex_path):
        return findings
    content = open(tex_path, "r", encoding="utf-8").read()
    # 找 resizebox 包裹的 tabular
    for m in re.finditer(
        r'\\resizebox\{\\(columnwidth|textwidth)\}\{!\}\{%\s*\\begin\{tabular\}\{([^}]+)\}',
        content
    ):
        width_cmd = m.group(1)
        col_spec = m.group(2)
        # 数列数（| 分隔的 l/c/r）
        n_cols = len(re.findall(r'[lcr]', col_spec))
        # columnwidth + 9 列 → 必然缩太小
        if width_cmd == "columnwidth" and n_cols >= 7:
            findings.append(_make_finding(
                source="table_checker", kind="overshrunk",
                severity="warning", location_chapter="main.tex",
                target=f"\\resizebox{{\\columnwidth}} {n_cols}列表格",
                evidence=f"resizebox columnwidth + {n_cols}列 → 字号过小",
                fix_hint=f"{n_cols}列表格用\\resizebox{{\\textwidth}}或\\small字号+自然宽度，避免强缩到不可读",
            ))
        elif width_cmd == "textwidth" and n_cols >= 10:
            findings.append(_make_finding(
                source="table_checker", kind="overshrunk",
                severity="info", location_chapter="main.tex",
                target=f"\\resizebox{{\\textwidth}} {n_cols}列表格",
                evidence=f"resizebox textwidth + {n_cols}列 → 可能偏小",
                fix_hint=f"{n_cols}列表格考虑横向排列或拆分，避免缩太小",
            ))
    if findings:
        logger.info(f"[TableChecker] {len(findings)} 条表格可读性问题（resizebox强缩）")
    return findings


# ═══════════════════════════════════════════════════════════════
# FigureInspector — 图尺寸/版式适配检查
# ═══════════════════════════════════════════════════════════════

def inspect_figures(tex_path: str, figures_dir: str) -> List:
    """检查图的实际渲染宽度 vs includegraphics 分配宽度。

    问题：横向多节点流图（TikZ min_width×N + 间距）生成时宽度可能 > textwidth，
    \\includegraphics[width=\\textwidth] 会等比缩放但节点拥挤重叠。
    """
    findings = []
    if not os.path.exists(tex_path):
        return findings
    content = open(tex_path, "r", encoding="utf-8").read()
    # 找所有 includegraphics
    for m in re.finditer(
        r'\\includegraphics\[width=\\(\w+)\]\{figures/([^}]+)\}',
        content
    ):
        width_cmd = m.group(1)
        fig_file = m.group(2)
        # 查对应的 TikZ source（如果有）
        base = re.sub(r'\.\w+$', '', fig_file)
        source_path = os.path.join(figures_dir, f"{base}_source.tex")
        if not os.path.exists(source_path):
            continue
        source = open(source_path, "r", encoding="utf-8").read()
        # 数横向节点数（\node ... right= ... of 的链式）
        right_of = len(re.findall(r'right\s*=\s*[\d.]+cm\s+of', source))
        # 数 min_width
        mw_match = re.findall(r'minimum\s+width\s*=\s*([\d.]+)cm', source)
        if right_of >= 4 and mw_match:
            avg_mw = sum(float(x) for x in mw_match) / len(mw_match)
            # 估算总宽：节点数 × min_width + 间距(~1.4cm × 节点数)
            est_width = (right_of + 1) * avg_mw + right_of * 1.4
            # textwidth ~17.8cm (IEEE double), columnwidth ~8.8cm
            limit = 17.8 if width_cmd == "textwidth" else 8.8
            if est_width > limit:  # 超出分配宽度即报（宁严勿松，TikZ 实际渲染含padding/标签会更宽）
                findings.append(_make_finding(
                    source="figure_inspector", kind="layout_overflow",
                    severity="warning", location_chapter="main.tex",
                    target=f"{fig_file} (width=\\{width_cmd})",
                    evidence=f"横向{right_of+1}节点流，估算宽{est_width:.1f}cm > {width_cmd}({limit}cm)",
                    fix_hint=f"横向流图{right_of+1}节点塞不进\\{width_cmd}，建议：缩节点min_width到{avg_mw*0.7:.1f}cm 或改纵向布局或用\\textwidth",
                ))
    if findings:
        logger.info(f"[FigureInspector] {len(findings)} 条图版式适配问题（横向流超宽）")
    return findings


# ═══════════════════════════════════════════════════════════════
# 统一入口：跑全部 Checker
# ═══════════════════════════════════════════════════════════════

def inspect_language(tex_path: str) -> List:
    """检查全文语言一致性（术语/时态/语态）。

    职能边界：只审不改，报 Finding。
    检查项：
    - 时态一致性（Methodology 应用现在时，Experiments 结果用过去时）
    - 术语统一（同一概念是否用了多个写法，如 "depth map" vs "disparity map"）
    - 被动/主动语态滥用
    """
    findings = []
    if not os.path.exists(tex_path):
        return findings
    content = open(tex_path, "r", encoding="utf-8").read()
    import re

    # 1. 时态：Experiments 章节里 "we proposes"（现在时第三人称错用）
    exp_section = re.search(r'\\section\{.*?[Ee]xperiment.*?\}(.*?)(?=\\section|$)',
                            content, re.DOTALL)
    if exp_section:
        exp_text = exp_section.group(1)
        # 过去时该用 achieved/demonstrated/showed，现在时 proposes/achieves 在 Experiments 是错的
        wrong_tense = re.findall(r'\b(we|our method|our approach)\s+(proposes|achieves|shows|demonstrates)\b',
                                 exp_text, re.IGNORECASE)
        if wrong_tense:
            findings.append(_make_finding(
                source="language_reviewer", kind="tense_inconsistency",
                severity="info", location_chapter="Experiments",
                target=f"Experiments 时态",
                evidence=f"Experiments 应过去时，发现 {len(wrong_tense)} 处现在时",
                fix_hint="Experiments 结果描述应用过去时(achieved/demonstrated/showed)",
            ))

    # 2. 术语统一：常见同义词对（只报，不自动改——需语义判断）
    term_pairs = [
        (r"depth map", r"disparity map", "depth/disparity"),
        (r"light field", r"light-field", "light field 连字符"),
        (r"non-Lambertian", r"non-lambertian|Non-lambertian", "Non-Lambertian 大小写"),
    ]
    for pat1, pat2, label in term_pairs:
        c1 = len(re.findall(pat1, content, re.IGNORECASE))
        c2 = len(re.findall(pat2, content, re.IGNORECASE))
        if c1 > 0 and c2 > 0:  # 混用就报（不要求数量不等）
            findings.append(_make_finding(
                source="language_reviewer", kind="terminology_inconsistency",
                severity="info", location_chapter="main.tex",
                target=f"术语 {label}",
                evidence=f"'{label}' 有 {c1}+{c2} 种写法混用",
                fix_hint=f"统一 '{label}' 的写法（全文一致）",
            ))

    if findings:
        logger.info(f"[LanguageReviewer] {len(findings)} 条语言一致性问题")
    return findings


def run_all_vertical_checks(output_dir: str) -> List:
    """跑全部纵向 Checker，返回所有 Finding。

    在 phase8 编译前调用：4 个 Checker 审 → Finding → FixExecutor 改 → 重编译。
    """
    tex_path = os.path.join(output_dir, "latex", "main.tex")
    bib_path = os.path.join(output_dir, "latex", "references.bib")
    figures_dir = os.path.join(output_dir, "figures")
    all_findings = []
    all_findings.extend(inspect_bib(bib_path))
    all_findings.extend(inspect_formulas(tex_path))
    all_findings.extend(inspect_tables(tex_path))
    all_findings.extend(inspect_figures(tex_path, figures_dir))
    all_findings.extend(inspect_language(tex_path))
    if all_findings:
        logger.info(f"[VerticalCheckers] 共发现 {len(all_findings)} 条问题")
    return all_findings
