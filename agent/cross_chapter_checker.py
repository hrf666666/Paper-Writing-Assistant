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

    def check_all(self, chapters: Dict[int, str], abstract: str = "") -> Tuple[List[Dict], Dict[int, str], str]:
        """
        执行全部跨章节一致性检查

        v14: 返回 (issues, fixed_chapters, fixed_abstract)。
        如果有 paper_context，数值矛盾会被自动修复到 fixed_chapters/fixed_abstract 中。

        Args:
            chapters: {chapter_num: content}
            abstract: 摘要内容

        Returns:
            (一致性问题列表, 修复后的 chapters dict, 修复后的 abstract)
        """
        self.issues = []
        self._fixes_applied = []

        # 深拷贝 chapters 以避免修改原始数据
        import copy
        fixed_chapters = copy.deepcopy(chapters)
        fixed_abstract = abstract  # str 不可变，用变量承接修复结果

        checks = [
            ("section_references", lambda: self._check_section_references(fixed_chapters)),
            ("numerical_consistency", lambda: self._fix_numerical_consistency(fixed_chapters, fixed_abstract)),
            ("format_consistency", lambda: self._check_format_consistency(fixed_chapters)),
            ("citation_continuity", lambda: self._check_citation_continuity(fixed_chapters)),
        ]

        for name, check_fn in checks:
            try:
                result = check_fn()
                # numerical_consistency 返回修复后的 abstract
                if name == "numerical_consistency" and isinstance(result, str):
                    fixed_abstract = result
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

        return self.issues, fixed_chapters, fixed_abstract

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
        # 只统计整数章节号；忽略扩展章节的 str 键（如 "5_1"、"5_2"），
        # 因为 Python 的 int("5_1") 会忽略下划线返回 51，污染最大章号判断。
        chapter_nums = [
            int(k) for k in chapters.keys()
            if isinstance(k, int) or (isinstance(k, str) and k.isdigit())
        ]
        max_chapter = max(chapter_nums) if chapter_nums else 0

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

    def _fix_numerical_consistency(self, chapters: Dict[int, str], abstract: str) -> str:
        """
        检查并修复数值在不同章节之间的一致性。

        v14: 真正执行替换（原 v11.2 只记录不应用）。
        用 PaperContext metrics 作为权威数值源，替换不一致的数值。
        返回修复后的 abstract（chapters 直接 mutate fixed_chapters）。
        """
        fixed_abstract = abstract

        # 提取 Experiments 中的关键数值
        experiments = chapters.get(4, "")
        if not experiments:
            return fixed_abstract

        # 从 Experiments 提取 "Ours" 行的所有数值
        ours_values = {}
        for line in experiments.split('\n'):
            if re.search(r'[Oo]urs', line):
                for num_match in re.finditer(r'(\d+\.\d+)', line):
                    val = num_match.group(1)
                    ours_values[val] = ours_values.get(val, 0) + 1

        # 检查并修复 Abstract 中的不一致数值
        if fixed_abstract:
            abstract_numbers = re.findall(r'(\d+\.\d+)', fixed_abstract)
            for num in abstract_numbers:
                try:
                    found = any(abs(float(num) - float(v)) < 0.01 for v in ours_values)
                except (ValueError, TypeError):
                    found = False
                if not found and ours_values:
                    canonical = self._find_canonical_value(num, ours_values)
                    if canonical and canonical != num:
                        # v14: 真正执行替换（原来只记录）
                        fixed_abstract = fixed_abstract.replace(num, canonical)
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

        # v14: 检查并修复所有章节的数值（原来 body 为空）
        pc_metrics = self._paper_context.get("metrics", {})
        if pc_metrics:
            for ch_key, content in chapters.items():
                if not content:
                    continue
                fixed_content = content
                for metric_name, canonical_val in pc_metrics.items():
                    canonical_str = str(canonical_val)
                    try:
                        canonical_num = float(canonical_val)
                    except (ValueError, TypeError):
                        continue
                    # 找章节中与 canonical 近似但不一致的数值
                    for num_match in re.finditer(r'(\d+\.\d+)', fixed_content):
                        wrong = num_match.group(1)
                        try:
                            wrong_num = float(wrong)
                        except ValueError:
                            continue
                        # 差值在 20% 内但不一致 → 替换
                        if (abs(wrong_num - canonical_num) / max(abs(canonical_num), 0.001) < 0.2
                                and abs(wrong_num - canonical_num) > 0.001):
                            fixed_content = fixed_content.replace(wrong, canonical_str)
                            self._fixes_applied.append({
                                "type": "numerical_fix",
                                "description": f"Ch{ch_key} 数值 {wrong} → {canonical_str}（{metric_name}）",
                                "old": wrong,
                                "new": canonical_str,
                                "location": f"Chapter {ch_key}",
                            })
                if fixed_content != content:
                    chapters[ch_key] = fixed_content  # mutate fixed_chapters

        return fixed_abstract

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
        """v14: 检查 \cite{key} 引用的格式完整性。

        v14 LLM 直出 \cite{key}，不再有 [N] 编号。此检查改为：
        1. 检测空 key \cite{} 或格式异常的引用
        2. 检测残留的 [?] / [N] 标记（v14 不应出现）
        注：\cite{key} 是否在 references.bib 中可解析，由 Phase 7.8 的
        _ensure_bib_has_all_cited_keys 保证，此处不重复检查。
        """
        valid_chapters = {k: v for k, v in chapters.items() if v}
        if not valid_chapters:
            return
        full_text = "\n".join(valid_chapters.values())

        # 1. 检测空 key \cite{} （LLM 输出缺陷）
        empty_cites = len(re.findall(r'\\cite\{\s*\}', full_text))
        if empty_cites > 0:
            self.issues.append({
                "severity": "critical",
                "type": "empty_citation",
                "description": f"存在 {empty_cites} 个空引用 \\cite{{}}（key 缺失）",
                "location": "全文",
            })

        # 2. 检测残留的 [?] 标记
        unresolved = full_text.count("[?]")
        if unresolved > 0:
            self.issues.append({
                "severity": "critical",
                "type": "unresolved_citations",
                "description": f"存在 {unresolved} 个未解析的引用标记 [?]",
                "location": "全文",
            })

        # 3. 检测残留的 [N] 数字引用（v14 应全部为 \cite{}）
        numeric_refs = re.findall(r'\[(\d+)\]', full_text)
        if numeric_refs:
            self.issues.append({
                "severity": "warning",
                "type": "legacy_numeric_ref",
                "description": f"存在 {len(numeric_refs)} 个旧式 [N] 数字引用（v14 应为 \\cite{{key}}）",
                "location": "全文",
            })

    def get_critical_count(self) -> int:
        """获取严重问题数量"""
        return sum(1 for i in self.issues if i.get("severity") == "critical")
