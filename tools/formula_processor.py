# -*- coding: utf-8 -*-
"""
公式处理器 - 将 <formula> 标记转换为标准 Markdown/LaTeX 公式

解决问题：
1. 所有章节 prompt 要求用 <formula> 包裹公式，但 pipeline 无处理器
2. 最终输出保留原始 <formula> 标签，导致公式无法渲染
3. 公式无编号、无交叉引用

设计：
- <formula>简单公式</formula> → $简单公式$（行内）
- <formula>多行公式</formula> → $$...$$（行间）
- 自动检测是否需要 equation 环境
- 为行间公式添加编号（Eq. N）
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# 全局公式计数器（每篇论文重置）
_formula_counter = 0


def reset_formula_counter():
    """重置公式计数器（每篇论文开始时调用）"""
    global _formula_counter
    _formula_counter = 0


def process_formulas(text: str, auto_number: bool = True) -> str:
    """
    处理全文的 <formula> 标记，转换为标准 Markdown 数学格式

    Args:
        text: 包含 <formula> 标记的文本
        auto_number: 是否为行间公式自动编号

    Returns:
        处理后的文本（无 <formula> 残留）
    """
    global _formula_counter

    if '<formula>' not in text:
        return text

    def replace_formula(match):
        global _formula_counter
        formula = match.group(1).strip()

        if not formula:
            return ''

        # 判断是行内还是行间公式
        is_display = _is_display_formula(formula)

        if is_display:
            _formula_counter += 1
            eq_num = _formula_counter

            # 清理公式内容
            formula = _clean_formula(formula)

            if auto_number:
                return f'$$\n{formula}\n$$ {{: data-eq="{eq_num}" }}\n'
            else:
                return f'$$\n{formula}\n$$\n'
        else:
            formula = _clean_formula(formula)
            # 行内公式：去掉换行
            formula = formula.replace('\n', ' ')
            return f'${formula}$'

    result = re.sub(r'<formula>(.*?)</formula>', replace_formula, text, flags=re.DOTALL)

    # 处理可能遗漏的情况：<formula> 跨多行包含子公式
    result = re.sub(r'<formula>(.*?)</formula>', replace_formula, result, flags=re.DOTALL)

    logger.info(f"[formula_processor] 处理了 {_formula_counter} 个公式")
    return result


def _is_display_formula(formula: str) -> bool:
    """判断是否是行间公式（需要独立显示）"""
    # 多行公式
    if '\n' in formula:
        return True
    # 长公式
    if len(formula) > 80:
        return True
    # 包含 LaTeX 环境命令
    display_indicators = [
        '\\begin{', '\\end{', '\\aligned', '\\cases',
        '\\split', '\\gathered', '\\array',
        '\\\\',  # 换行符
        '\\sum', '\\int', '\\prod', '\\frac', '\\dfrac',
        '\\mathbf', '\\boldsymbol',
        '\\label{', '\\nonumber',
    ]
    for indicator in display_indicators:
        if indicator in formula:
            return True
    return False


def _clean_formula(formula: str) -> str:
    """清理公式内容"""
    # 去除首尾空白
    formula = formula.strip()
    # 移除可能残留的 Markdown 格式标记
    formula = re.sub(r'^```+\w*\n?', '', formula)
    formula = re.sub(r'\n?```+$', '', formula)
    return formula


def strip_formula_tags(text: str) -> str:
    """
    简单去除 <formula> 标签（fallback 模式）
    保留公式内容，用 $...$ 包裹
    """
    def simple_replace(match):
        formula = match.group(1).strip()
        if not formula:
            return ''
        if _is_display_formula(formula):
            return f'$${formula}$$'
        return f'${formula}$'

    return re.sub(r'<formula>(.*?)</formula>', simple_replace, text, flags=re.DOTALL)


def get_formula_count() -> int:
    """获取当前公式计数"""
    return _formula_counter


def process_full_paper(full_text: str) -> Tuple[str, dict]:
    """
    处理完整论文的所有公式

    Returns:
        (processed_text, stats)
    """
    reset_formula_counter()

    original_count = len(re.findall(r'<formula>', full_text))
    processed = process_formulas(full_text, auto_number=True)
    remaining = len(re.findall(r'<formula>', processed))

    stats = {
        "total_formulas": original_count,
        "processed": original_count - remaining,
        "remaining_tags": remaining,
        "numbered_equations": _formula_counter,
    }

    if remaining > 0:
        logger.warning(f"[formula_processor] 仍有 {remaining} 个 <formula> 标签未处理")
        # 二次尝试：用简单模式处理残留
        processed = strip_formula_tags(processed)

    return processed, stats
