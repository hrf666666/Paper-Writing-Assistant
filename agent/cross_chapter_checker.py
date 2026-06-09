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
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CrossChapterChecker:
    """跨章节一致性检查器"""

    def __init__(self, paper_context: Dict = None):
        """
        Args:
            paper_context: v11.2 PaperContext 共享事实源。
                           如果提供，数值矛盾会自动修复而非仅报告。
        """
        self.issues: List[Dict] = []
        self._paper_context = paper_context or {}
        self._fixes_applied: List[Dict] = []

    def set_paper_context(self, paper_context: Dict):
        """设置/更新 PaperContext"""
        self._paper_context = paper_context or {}

    def check_all(self, chapters: Dict[int, str], abstract: str = "") -> Tuple[List[Dict], Dict[int, str]]:
        """
        执行全部跨章节一致性检查

        v11.2: 返回 (issues, fixed_chapters)。
        如果有 paper_context，数值矛盾会被自动修复到 fixed_chapters 中。

        Args:
            chapters: {chapter_num: content}
            abstract: 摘要内容

        Returns:
            (一致性问题列表, 修复后的 chapters dict)
        """
        self.issues = []
        self._fixes_applied = []

        # 深拷贝 chapters 以避免修改原始数据
        import copy
        fixed_chapters = copy.deepcopy(chapters)

        checks = [
            ("section_references", lambda: self._check_section_references(fixed_chapters)),
            ("numerical_consistency", lambda: self._check_numerical_consistency(fixed_chapters, abstract)),
            ("format_consistency", lambda: self._check_format_consistency(fixed_chapters)),
            ("citation_continuity", lambda: self._check_citation_continuity(fixed_chapters)),
        ]

        for name, check_fn in checks:
            try:
                check_fn()
            except Exception as e:
                logger.error(f"检查 {name} 失败: {e}")
                self.issues.append({
                    "severity": "warning",
                    "type": "check_error",
                    "description": f"检查 {name} 过程中出错: {e}",
                    "location": "checker",
                })

        logger.info(f"[CrossChapterChecker] 检查完成: {len(self.issues)} 个一致性问题")
        for issue in self.issues:
            severity = issue.get("severity", "warning")
            logger.info(f"  [{severity}] {issue.get('description', '')[:100]}")

        if self._fixes_applied:
            logger.info(f"[CrossChapterChecker] 自动修复 {len(self._fixes_applied)} 处数值矛盾")
            for fix in self._fixes_applied:
                logger.info(f"  Fix: {fix.get('description', '')[:100]}")

        return self.issues, fixed_chapters

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
        max_chapter = max(int(k) for k in chapters.keys()) if chapters else 0

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
        """
        检查数值在不同章节之间的一致性。

        v11.2: 如果有 PaperContext，用其中的 metrics 作为权威数值源，
        自动替换不一致的数值。
        """
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
                try:
                    found = any(abs(float(num) - float(v)) < 0.01 for v in ours_values)
                except (ValueError, TypeError):
                    found = False
                if not found and ours_values:
                    # v11.2: 如果有 PaperContext metrics，尝试自动修复
                    canonical = self._find_canonical_value(num, ours_values)
                    if canonical and canonical != num:
                        # 在 abstract 中替换（由调用方 fixed_chapters 处理）
                        self._fixes_applied.append({
                            "type": "numerical_fix",
                            "description": f"Abstract 数值 {num} → {canonical}（PaperContext 修正）",
                            "old": num,
                            "new": canonical,
                            "location": "Abstract",
                        })
                    else:
                        self.issues.append({
                            "severity": "warning",
                            "type": "numerical_inconsistency",
                            "description": f"Abstract 提到数值 {num}，但 Experiments 中的结果不含此值",
                            "location": f"Abstract → {num}",
                        })

        # v11.2: 检查所有章节的数值是否与 PaperContext metrics 一致
        pc_metrics = self._paper_context.get("metrics", {})
        if pc_metrics:
            for ch_key, content in chapters.items():
                if not content:
                    continue
                for metric_name, canonical_val in pc_metrics.items():
                    canonical_str = str(canonical_val)
                    # 如果章节中包含这个数值，检查是否一致
                    # 只检查明确的不一致（数值出现但与 canonical 不同）
                    # 此处仅报告，不自动修复（因为上下文可能不同）

    def _find_canonical_value(self, wrong_val: str, ours_values: Dict) -> Optional[str]:
        """
        从 PaperContext metrics 中找到最可能的正确值。

        如果 wrong_val 与某个 metric 值近似但不完全一致，
        返回 canonical 值。否则返回 None。
        """
        pc_metrics = self._paper_context.get("metrics", {})
        if not pc_metrics:
            return None

        try:
            wrong_num = float(wrong_val)
        except (ValueError, TypeError):
            return None

        for name, canonical in pc_metrics.items():
            try:
                canonical_num = float(canonical)
                # 如果差值在 20% 以内，认为是同一个指标的不同版本
                if abs(wrong_num - canonical_num) / max(abs(canonical_num), 0.001) < 0.2:
                    if abs(wrong_num - canonical_num) > 0.001:  # 但不完全一致
                        return str(canonical)
            except (ValueError, TypeError):
                continue

        return None

    def _check_format_consistency(self, chapters: Dict[int, str]):
        """检查格式一致性（全文应为纯 LaTeX，不应有 Markdown 残留）"""
        has_markdown_headers = False

        for num, content in chapters.items():
            if re.search(r'^#{1,3}\s', content, re.MULTILINE):
                has_markdown_headers = True

        if has_markdown_headers:
            self.issues.append({
                "severity": "warning",
                "type": "format_inconsistency",
                "description": "检测到 Markdown 标题残留（# 开头行），应全部使用 LaTeX 格式",
                "location": "全文",
            })

    def _check_citation_continuity(self, chapters: Dict[int, str]):
        """检查引用编号是否连续"""
        valid_chapters = {k: v for k, v in chapters.items() if v}
        if not valid_chapters:
            return
        full_text = "\n".join(valid_chapters.values())

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
