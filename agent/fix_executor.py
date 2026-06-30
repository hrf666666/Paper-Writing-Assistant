# -*- coding: utf-8 -*-
"""fix_executor — v16.3 统一修复执行器（执行机构）。

分层治理架构第4层：按 Finding 的 source/kind 路由到对应修复。
**只执行不改判**，改完交回调用方（由 Verifier 验收）。

修复能力（本轮，确定性修复优先）：
  - bib author 全名→Last,First 转换（确定性，无需 LLM）
  - 表格 resizebox columnwidth→textwidth（7+列表格，确定性）
  - 公式超界：注入 split/multline（需 LLM，本轮记录待修不自动执行）
  - 图重叠：重画（需 figure_generator，本轮记录待修不自动执行）

设计原则：
  - 只改不判：按 Finding 的 fix 建议执行，不自己评估对错
  - 确定性优先：能正则/规则修的不调 LLM
  - 返回修复结果：{finding_id, fixed: bool, method, detail}
"""
import os
import re
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


def execute_fix(finding, output_dir: str) -> Dict:
    """按单条 Finding 执行修复。

    Args:
        finding: Finding 对象（带 fix: FixAction）
        output_dir: output 目录

    Returns:
        {finding_id, fixed: bool, method: str, detail: str}
    """
    fid = finding.id
    source = finding.source
    kind = finding.kind

    # 路由到对应修复器
    if source == "bib_inspector" and kind == "author_format":
        return _fix_bib_author(finding, output_dir)
    elif source == "table_checker" and kind == "overshrunk":
        return _fix_table_resizebox(finding, output_dir)
    elif source == "formula_checker" and kind == "overflow":
        return _fix_formula_overflow(finding, output_dir)
    elif source == "figure_inspector" and kind == "layout_overflow":
        return _fix_figure_layout(finding, output_dir)
    else:
        return {"finding_id": fid, "fixed": False, "method": "skip",
                "detail": f"无自动修复器 for {source}/{kind}"}


def execute_fixes(findings: List, output_dir: str) -> List[Dict]:
    """批量执行修复。"""
    results = []
    for f in findings:
        results.append(execute_fix(f, output_dir))
    fixed_n = sum(1 for r in results if r["fixed"])
    logger.info(f"[FixExecutor] 处理 {len(findings)} 条 Finding，修复 {fixed_n} 条")
    return results


# ═══════════════════════════════════════════════════════════════
# 确定性修复器
# ═══════════════════════════════════════════════════════════════

def _fix_bib_author(finding, output_dir: str) -> Dict:
    """修复 bib author 全名→Last,First 格式（确定性）。

    finding.fix.hint 格式: "author={Last, First and Last2, First2}"
    直接在 bib 文件里替换对应条目的 author 字段。
    """
    bib_path = os.path.join(output_dir, "latex", "references.bib")
    if not os.path.exists(bib_path):
        return {"finding_id": finding.id, "fixed": False, "method": "skip",
                "detail": "references.bib 不存在"}
    # 从 hint 提取正确的 author 串
    hint = finding.fix.hint if finding.fix else ""
    m = re.match(r'author=\{(.+)\}', hint)
    if not m:
        return {"finding_id": finding.id, "fixed": False, "method": "skip",
                "detail": "无法从 hint 提取 author 串"}
    correct_author = m.group(1)
    # bib key（从 location.raw 取 @key）
    bib_key = finding.location.raw.lstrip('@')
    # 读 bib，替换该条目的 author
    content = open(bib_path, "r", encoding="utf-8").read()
    # 找 @type{key, ... author={...} ... }
    pattern = re.compile(
        r'(@\w+\{' + re.escape(bib_key) + r',.*?author\s*=\s*\{)([^}]+)(\})',
        re.DOTALL
    )
    new_content, n = pattern.subn(
        lambda m: m.group(1) + correct_author + m.group(3), content, count=1
    )
    if n == 0:
        return {"finding_id": finding.id, "fixed": False, "method": "skip",
                "detail": f"未找到 @{bib_key} 的 author 字段"}
    with open(bib_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return {"finding_id": finding.id, "fixed": True, "method": "bib_author_format",
            "detail": f"@{bib_key}: author → {correct_author[:50]}"}


def _fix_table_resizebox(finding, output_dir: str) -> Dict:
    """修复表格 resizebox columnwidth→textwidth（7+列表格，确定性）。"""
    tex_path = os.path.join(output_dir, "latex", "main.tex")
    if not os.path.exists(tex_path):
        return {"finding_id": finding.id, "fixed": False, "method": "skip", "detail": "main.tex 不存在"}
    content = open(tex_path, "r", encoding="utf-8").read()
    # 把 7+列表格的 resizebox columnwidth → textwidth
    # 找 resizebox{columnwidth}{!}{\begin{tabular}{列数>=7}}
    def _fix(m):
        col_spec = m.group(1)
        n_cols = len(re.findall(r'[lcr]', col_spec))
        if n_cols >= 7:
            return m.group(0).replace(r'\columnwidth', r'\textwidth')
        return m.group(0)
    new_content, n = re.subn(
        r'\\resizebox\{\\columnwidth\}\{!\}\{%\s*\\begin\{tabular\}\{([^}]+)\}',
        _fix, content
    )
    if n == 0 or new_content == content:
        return {"finding_id": finding.id, "fixed": False, "method": "skip",
                "detail": "未找到匹配的 resizebox"}
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return {"finding_id": finding.id, "fixed": True, "method": "table_resizebox",
            "detail": "7+列表格 resizebox columnwidth→textwidth"}


# ═══════════════════════════════════════════════════════════════
# 需 LLM 的修复器（本轮记录，不自动执行）
# ═══════════════════════════════════════════════════════════════

def _fix_formula_overflow(finding, output_dir: str) -> Dict:
    """公式超界修复（需 LLM 注入 split/multline）。本轮记录待修。"""
    return {"finding_id": finding.id, "fixed": False, "method": "llm_pending",
            "detail": "公式换行需 LLM（下轮实现），当前记录为待修"}


def _fix_figure_layout(finding, output_dir: str) -> Dict:
    """图布局修复（需 figure_generator 重画）。本轮记录待修。"""
    return {"finding_id": finding.id, "fixed": False, "method": "llm_pending",
            "detail": "图重排需 figure_generator（下轮实现），当前记录为待修"}
