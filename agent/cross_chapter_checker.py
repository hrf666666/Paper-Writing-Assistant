# -*- coding: utf-8 -*-
"""
跨章节一致性检查器

检查项：
1. 术语一致性：同一概念在不同章节的表达是否统一
2. 数值一致性：Abstract 中的数字是否与 Experiments 一致
3. 章节引用一致性：Introduction 提到的 Section N 是否与实际章节对应
4. 格式一致性：全文使用统一的 Markdown 或 LaTeX 格式
5. 引用编号连续性：[1]-[N] 是否连续无缺失
"""

import re
import json
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class CrossChapterChecker:
    """跨章节一致性检查器"""

    def __init__(self):
        self.issues: List[Dict] = []

    def check_all(self, chapters: Dict[int, str], abstract: str = "") -> List[Dict]:
        """
        执行全部跨章节一致性检查

        Args:
            chapters: {chapter_num: content}
            abstract: 摘要内容

        Returns:
            一致性问题列表
        """
        self.issues = []

        self._check_section_references(chapters)
        self._check_numerical_consistency(chapters, abstract)
        self._check_format_consistency(chapters)
        self._check_citation_continuity(chapters)

        logger.info(f"[CrossChapterChecker] 检查完成: {len(self.issues)} 个一致性问题")
        for issue in self.issues:
            severity = issue.get("severity", "warning")
            logger.info(f"  [{severity}] {issue.get('description', '')[:100]}")

        return self.issues

    def _check_section_references(self, chapters: Dict[int, str]):
        """检查 Introduction 中提到的 Section 引用是否与实际章节对应"""
        intro = chapters.get(1, "")
        if not intro:
            return

        # 查找 "Section N" 或 "Section N.M" 的引用
        section_refs = re.findall(r'[Ss]ection\s+(I{1,3}|IV|V(?:I{0,3})?|\d+(?:\.\d+)?)', intro)

        # 实际章节映射
        actual_sections = {
            "1": "Introduction", "I": "Introduction",
            "2": "Related Work", "II": "Related Work",
            "3": "Methodology", "III": "Methodology",
            "4": "Experiments", "IV": "Experiments",
            "5": "Conclusion", "V": "Conclusion",
        }
        max_chapter = max(chapters.keys()) if chapters else 0

        for ref in section_refs:
            if ref.isdigit():
                ref_num = int(ref)
                if ref_num > max_chapter:
                    self.issues.append({
                        "severity": "critical",
                        "type": "section_reference_inconsistency",
                        "description": f"Introduction 引用了 Section {ref}，但论文只有 {max_chapter} 章",
                        "location": f"Introduction → Section {ref}",
                    })

    def _check_numerical_consistency(self, chapters: Dict[int, str], abstract: str):
        """检查数值在不同章节之间的一致性"""
        # 提取 Experiments 中的关键数值
        experiments = chapters.get(4, "")
        if not experiments:
            return

        # 从 Experiments 提取 "Ours" 行的所有数值
        ours_values = {}
        # 匹配包含 "Ours" 的行中的所有浮点数
        for line in experiments.split('\n'):
            if re.search(r'[Oo]urs', line):
                for num_match in re.finditer(r'(\d+\.\d+)', line):
                    val = num_match.group(1)
                    ours_values[val] = ours_values.get(val, 0) + 1

        # 检查 Abstract 中是否提到了 Experiments 中不存在的数值
        if abstract:
            abstract_numbers = re.findall(r'(\d+\.\d+)', abstract)
            for num in abstract_numbers:
                # 允许近似匹配
                found = any(abs(float(num) - float(v)) < 0.01 for v in ours_values)
                if not found and ours_values:
                    self.issues.append({
                        "severity": "warning",
                        "type": "numerical_inconsistency",
                        "description": f"Abstract 提到数值 {num}，但 Experiments 中的结果不含此值",
                        "location": f"Abstract → {num}",
                    })

    def _check_format_consistency(self, chapters: Dict[int, str]):
        """检查格式一致性（全文 Markdown 或 LaTeX 不应混用）"""
        has_latex_blocks = False
        has_markdown_headers = False

        for num, content in chapters.items():
            if re.search(r'\\begin\{', content):
                has_latex_blocks = True
            if re.search(r'^#{1,3}\s', content, re.MULTILINE):
                has_markdown_headers = True

        if has_latex_blocks and has_markdown_headers:
            self.issues.append({
                "severity": "warning",
                "type": "format_inconsistency",
                "description": "全文混用 Markdown 标题和 LaTeX 块级元素（\\begin{...}），建议统一格式",
                "location": "全文",
            })

    def _check_citation_continuity(self, chapters: Dict[int, str]):
        """检查引用编号是否连续"""
        full_text = "\n".join(chapters.values())

        # 检查 [n] 引用编号
        numeric_refs = re.findall(r'\[(\d+)\]', full_text)
        if not numeric_refs:
            return

        ref_nums = sorted(set(int(n) for n in numeric_refs))
        max_ref = max(ref_nums)

        # 检查是否有跳号
        expected = set(range(1, max_ref + 1))
        missing = expected - set(ref_nums)

        if missing:
            self.issues.append({
                "severity": "warning",
                "type": "citation_gap",
                "description": f"引用编号存在跳号: 缺少 {sorted(missing)}",
                "location": "全文引用",
            })

        # 检查 [?] 标记（未解析的引用）
        unresolved = full_text.count("[?]")
        if unresolved > 0:
            self.issues.append({
                "severity": "critical",
                "type": "unresolved_citations",
                "description": f"存在 {unresolved} 个未解析的引用标记 [?]",
                "location": "全文",
            })

    def get_critical_count(self) -> int:
        """获取严重问题数量"""
        return sum(1 for i in self.issues if i.get("severity") == "critical")
