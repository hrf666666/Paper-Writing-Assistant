# -*- coding: utf-8 -*-
"""
VERIFY 独立验证层 — 纯代码检查，零LLM成本

借鉴 auto_research_agent 的 VERIFY 阶段设计：
- 不调用任何 LLM，全部用规则和代码验证
- 检查结果可量化、可追踪、可复现
- 每个检查函数返回 (passed: bool, details: dict)

检查项：
V1. 引用完整性：每个 [N] 是否有对应 reference 条目
V2. 数据一致性：Abstract 数值是否在 Experiments 中出现
V3. 公式语法：$...$ 和 $$...$$ 是否正确配对
V4. 段落去重：Jaccard 相似度检测重复段落
V5. 残留标记：无 [?], <formula>, <citation> 残留
V6. 章节引用："Section N" 是否对应实际章节
V7. 结构完整性：每个章节是否包含预期的子节
V8. 符号一致性：同一缩写在全文中含义是否一致（简单版）
"""

import re
import math
import logging
import difflib
from typing import Dict, List, Tuple, Optional, Any
from collections import Counter

logger = logging.getLogger(__name__)


class VerifyReport:
    """验证报告"""

    def __init__(self):
        self.checks: List[Dict[str, Any]] = []
        self.passed_count = 0
        self.failed_count = 0
        self.warning_count = 0

    @property
    def passed(self) -> bool:
        return self.failed_count == 0

    @property
    def total_score(self) -> float:
        """0-100 综合得分"""
        if not self.checks:
            return 0.0
        scores = [c.get("score", 0) for c in self.checks]
        return sum(scores) / len(scores) if scores else 0.0

    def add_check(self, name: str, passed: bool, score: float,
                  severity: str = "error", details: str = "",
                  fix_hint: str = ""):
        """添加一个检查结果"""
        self.checks.append({
            "name": name,
            "passed": passed,
            "score": score,
            "severity": severity,
            "details": details,
            "fix_hint": fix_hint,
        })
        if passed:
            self.passed_count += 1
        elif severity == "warning":
            self.warning_count += 1
        else:
            self.failed_count += 1

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "total_score": round(self.total_score, 1),
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "warning_count": self.warning_count,
            "checks": self.checks,
        }

    def get_failures(self) -> List[Dict]:
        """获取所有失败的检查项"""
        return [c for c in self.checks if not c["passed"] and c["severity"] == "error"]

    def get_fix_hints(self) -> List[str]:
        """获取所有修复建议"""
        return [c["fix_hint"] for c in self.checks if not c["passed"] and c["fix_hint"]]

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (f"[VERIFY] {status} | "
                f"score={self.total_score:.1f} | "
                f"passed={self.passed_count} "
                f"failed={self.failed_count} "
                f"warnings={self.warning_count}")


class ContentVerifier:
    """
    内容验证器 — 纯代码验证，不调用LLM

    用法:
        verifier = ContentVerifier()
        report = verifier.verify_all(chapters, abstract, bibliography)
        print(report.summary())
    """

    def __init__(self, reference_pool: List[Dict] = None):
        self.reference_pool = reference_pool or []

    def verify_all(self, chapters: Dict, abstract: str = "",
                   bibliography: str = "") -> VerifyReport:
        """
        执行全部验证检查

        Args:
            chapters: {chapter_key: content} 字典
            abstract: 摘要文本
            bibliography: 参考文献列表文本

        Returns:
            VerifyReport
        """
        report = VerifyReport()

        full_text = "\n\n".join(str(v) for v in chapters.values() if v)

        checks = [
            ("V1_citation_integrity", lambda: self._check_citation_integrity(
                full_text, bibliography)),
            ("V2_data_consistency", lambda: self._check_data_consistency(
                chapters, abstract)),
            ("V3_formula_syntax", lambda: self._check_formula_syntax(full_text)),
            ("V4_paragraph_dedup", lambda: self._check_paragraph_dedup(chapters)),
            ("V5_residual_markers", lambda: self._check_residual_markers(full_text)),
            ("V6_section_references", lambda: self._check_section_references(chapters)),
            ("V7_structure_completeness", lambda: self._check_structure_completeness(
                chapters)),
            ("V8_symbol_consistency", lambda: self._check_symbol_consistency(chapters)),
        ]

        for name, check_fn in checks:
            try:
                result = check_fn()
                report.add_check(
                    name=name,
                    passed=result["passed"],
                    score=result["score"],
                    severity=result.get("severity", "error"),
                    details=result.get("details", ""),
                    fix_hint=result.get("fix_hint", ""),
                )
            except Exception as e:
                logger.error(f"验证检查 {name} 异常: {e}")
                report.add_check(
                    name=name, passed=False, score=0,
                    severity="warning",
                    details=f"检查执行异常: {str(e)[:200]}",
                )

        logger.info(report.summary())
        return report

    # ──────────── V1: 引用完整性 ────────────

    def _check_citation_integrity(self, full_text: str,
                                   bibliography: str) -> Dict:
        """
        检查 [N] 引用是否完整：
        - 正文中的 [N] 编号是否在参考文献中有对应条目
        - 引用编号是否连续（无跳号）
        """
        # 提取正文中的引用编号
        refs_in_text = re.findall(r'\[(\d+)\]', full_text)

        # 检查 [?] 未解析引用（无论是否有 [N] 格式引用）
        unresolved = full_text.count("[?]")

        if not refs_in_text:
            if unresolved > 0:
                return {
                    "passed": False, "score": 0,
                    "details": f"存在 {unresolved} 个 [?] 未解析引用，无有效 [N] 引用",
                    "fix_hint": "运行 CitationManager 解析所有引用标记",
                }
            return {
                "passed": True, "score": 100,
                "details": "无 [N] 格式引用（可能尚未解析）",
            }

        ref_nums = sorted(set(int(n) for n in refs_in_text))
        max_ref = max(ref_nums)

        # 检查参考文献列表中的编号
        bib_refs = set()
        if bibliography:
            bib_nums = re.findall(r'^\[(\d+)\]', bibliography, re.MULTILINE)
            bib_refs = set(int(n) for n in bib_nums)

        # 计算：正文引用中，有多少在bibliography里有对应
        matched = sum(1 for n in ref_nums if n in bib_refs) if bib_refs else 0
        coverage = matched / len(ref_nums) if ref_nums else 1.0

        # 检查跳号
        expected = set(range(1, max_ref + 1))
        missing = expected - set(ref_nums)
        gap_penalty = len(missing) * 5

        score = max(0, min(100, coverage * 100 - gap_penalty - unresolved * 20))
        passed = unresolved == 0 and coverage >= 0.9 and len(missing) <= 2

        details_parts = []
        if unresolved > 0:
            details_parts.append(f"{unresolved} 个 [?] 未解析引用")
        if missing:
            details_parts.append(f"引用跳号: 缺 {sorted(missing)}")
        if coverage < 1.0 and bib_refs:
            details_parts.append(f"引用覆盖率 {coverage:.0%}")

        return {
            "passed": passed,
            "score": round(score, 1),
            "details": "; ".join(details_parts) if details_parts else "引用完整性检查通过",
            "fix_hint": "运行 CitationManager 解析引用，确保每个 [N] 都有对应参考文献条目" if not passed else "",
        }

    # ──────────── V2: 数据一致性 ────────────

    def _check_data_consistency(self, chapters: Dict,
                                 abstract: str) -> Dict:
        """
        检查 Abstract 中数值是否在 Experiments 中出现
        """
        if not abstract:
            return {"passed": True, "score": 100, "details": "无 Abstract 可检查"}

        experiments = ""
        for key in chapters:
            key_str = str(key)
            if key_str in ("4", "experiments", "Experiments"):
                experiments = chapters[key]
                break
        if not experiments:
            return {"passed": True, "score": 100, "details": "无 Experiments 章节可对照"}

        # 从 Experiments 提取数值集合
        exp_numbers = set(re.findall(r'\b(\d+\.\d+)\b', experiments))

        # 从 Abstract 提取数值
        abs_numbers = re.findall(r'\b(\d+\.\d+)\b', abstract)

        if not abs_numbers:
            return {"passed": True, "score": 100, "details": "Abstract 无数值"}

        # 检查 Abstract 数值是否在 Experiments 中
        mismatches = []
        for num in abs_numbers:
            try:
                num_val = float(num)
                found = any(abs(num_val - float(e)) < 0.02 for e in exp_numbers)
                if not found:
                    mismatches.append(num)
            except ValueError:
                pass

        if not mismatches:
            return {"passed": True, "score": 100, "details": "Abstract 数值与 Experiments 一致"}

        score = max(0, 100 - len(mismatches) * 15)
        return {
            "passed": len(mismatches) == 0,
            "score": score,
            "severity": "error" if len(mismatches) > 2 else "warning",
            "details": f"Abstract 中 {len(mismatches)} 个数值未在 Experiments 中找到: {mismatches[:5]}",
            "fix_hint": "将 Abstract 中的数值替换为 Experiments 表格中的实际数据",
        }

    # ──────────── V3: 公式语法 ────────────

    def _check_formula_syntax(self, full_text: str) -> Dict:
        """
        检查公式标记语法是否正确：
        - $...$ 行内公式配对
        - $$...$$ 行间公式配对
        - 无残留 <formula> 标记
        """
        issues = []

        # 检查残留 <formula> 标记
        formula_residual = len(re.findall(r'<formula>', full_text))
        if formula_residual > 0:
            issues.append(f"{formula_residual} 个残留 <formula> 标记")

        # 检查 $$ 配对
        # 先移除代码块中的内容避免误报
        text_no_code = re.sub(r'```.*?```', '', full_text, flags=re.DOTALL)
        display_dollars = text_no_code.count('$$')
        if display_dollars % 2 != 0:
            issues.append("$$ 公式标记不配对（奇数个 $$）")

        # 检查残留 <citation> 标记
        citation_residual = len(re.findall(r'<citation>', full_text))
        if citation_residual > 0:
            issues.append(f"{citation_residual} 个残留 <citation> 标记")

        if not issues:
            return {"passed": True, "score": 100, "details": "公式语法检查通过"}

        score = max(0, 100 - len(issues) * 20)
        return {
            "passed": formula_residual == 0 and citation_residual == 0,
            "score": score,
            "details": "; ".join(issues),
            "fix_hint": "运行 formula_processor 和 citation_manager 清理残留标记",
        }

    # ──────────── V4: 段落去重 ────────────

    def _check_paragraph_dedup(self, chapters: Dict) -> Dict:
        """
        检查章节之间和章节内部的段落重复
        使用 Jaccard 相似度
        """
        all_paragraphs = []
        for key, content in chapters.items():
            if not content or not isinstance(content, str):
                continue
            paras = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 50]
            for p in paras:
                all_paragraphs.append((key, p))

        # 两两比较（O(n²) 但段落数量有限）
        duplicates = []
        for i in range(len(all_paragraphs)):
            for j in range(i + 1, len(all_paragraphs)):
                key_i, para_i = all_paragraphs[i]
                key_j, para_j = all_paragraphs[j]

                # 跳过同一章节内的比较（内部去重由 deduplicate_content 处理）
                if key_i == key_j:
                    continue

                sim = self._jaccard_similarity(para_i, para_j)
                if sim > 0.6:
                    duplicates.append({
                        "chapters": f"{key_i} vs {key_j}",
                        "similarity": round(sim, 2),
                        "preview": para_i[:80],
                    })

        if not duplicates:
            return {"passed": True, "score": 100, "details": "未检测到跨章节段落重复"}

        high_dup = [d for d in duplicates if d["similarity"] > 0.8]
        score = max(0, 100 - len(high_dup) * 15 - len(duplicates) * 5)

        return {
            "passed": len(high_dup) == 0,
            "score": score,
            "severity": "warning" if not high_dup else "error",
            "details": f"发现 {len(duplicates)} 对相似段落（其中 {len(high_dup)} 对高度重复 > 0.8）",
            "fix_hint": "移除重复段落或合并到同一位置",
        }

    @staticmethod
    def _jaccard_similarity(text1: str, text2: str) -> float:
        """计算两个文本的 Jaccard 相似度（词级别）"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    # ──────────── V5: 残留标记 ────────────

    def _check_residual_markers(self, full_text: str) -> Dict:
        """
        检查所有不应出现在最终文本中的残留标记
        """
        markers = [
            (r'\[?\?\]', "未解析引用 [?]"),
            (r'<formula>', "残留 <formula> 标记"),
            (r'</formula>', "残留 </formula> 标记"),
            (r'<citation>', "残留 <citation> 标记"),
            (r'</citation>', "残留 </citation> 标记"),
            (r'\[ref\]', "未解析引用 [ref]"),
            (r'TBD|TODO|FIXME|XXX', "未完成标记"),
        ]

        found = []
        for pattern, desc in markers:
            count = len(re.findall(pattern, full_text, re.IGNORECASE))
            if count > 0:
                found.append(f"{desc}: {count} 处")

        if not found:
            return {"passed": True, "score": 100, "details": "无残留标记"}

        score = max(0, 100 - len(found) * 15)
        return {
            "passed": False,
            "score": score,
            "details": "发现残留标记: " + "; ".join(found),
            "fix_hint": "运行后处理清理所有残留标记",
        }

    # ──────────── V6: 章节引用 ────────────

    def _check_section_references(self, chapters: Dict) -> Dict:
        """
        检查 Introduction 中 "Section N" 引用是否与实际章节对应
        """
        intro = ""
        for key in chapters:
            if str(key) == "1":
                intro = chapters[key]
                break
        if not intro:
            return {"passed": True, "score": 100, "details": "无 Introduction 可检查"}

        # 提取 "Section N" 引用
        section_refs = re.findall(
            r'[Ss]ection\s+(I{1,3}|IV|V(?:I{0,3})?|\d+(?:\.\d+)?)', intro
        )

        max_chapter = 0
        for key in chapters:
            try:
                k = int(str(key).split("_")[0])
                max_chapter = max(max_chapter, k)
            except (ValueError, TypeError):
                pass

        invalid_refs = []
        for ref in section_refs:
            if ref.isdigit():
                ref_num = int(ref)
                if ref_num > max_chapter or ref_num < 1:
                    invalid_refs.append(f"Section {ref} (实际只有 {max_chapter} 章)")

        if not invalid_refs:
            return {"passed": True, "score": 100, "details": "章节引用正确"}

        score = max(0, 100 - len(invalid_refs) * 20)
        return {
            "passed": False,
            "score": score,
            "details": f"无效章节引用: {invalid_refs}",
            "fix_hint": f"修正 Introduction 中的 Section 引用，最大章节号为 {max_chapter}",
        }

    # ──────────── V7: 结构完整性 ────────────

    def _check_structure_completeness(self, chapters: Dict) -> Dict:
        """
        检查每个章节是否包含预期的子节标题
        """
        # 预期的章节结构
        expected = {
            1: ["introduction", "contributions"],
            2: ["related work", "literature"],
            3: ["method", "proposed", "approach", "framework"],
            4: ["experiment", "result", "evaluation", "ablation"],
            5: ["conclusion"],
        }

        missing = []
        checked = 0
        for ch_num, keywords in expected.items():
            content = chapters.get(ch_num, "")
            if not content:
                continue
            checked += 1
            content_lower = content.lower()
            # 至少有一个关键词应该出现在标题中
            has_section = any(
                re.search(r'#{1,3}\s+.*' + re.escape(kw), content_lower)
                for kw in keywords
            )
            if not has_section:
                # 放宽：只要内容中包含这些关键词也行
                has_mention = any(kw in content_lower for kw in keywords)
                if not has_mention:
                    missing.append(f"Chapter {ch_num} 缺少预期子节（关键词: {keywords[:2]}）")

        if not missing or checked == 0:
            return {"passed": True, "score": 100, "details": "结构完整性检查通过"}

        score = max(0, 100 - len(missing) * 20)
        return {
            "passed": len(missing) <= 1,
            "score": score,
            "severity": "warning",
            "details": "; ".join(missing),
            "fix_hint": "确保每个章节包含该章节应有的核心子节",
        }

    # ──────────── V8: 符号一致性 ────────────

    def _check_symbol_consistency(self, chapters: Dict) -> Dict:
        """
        简单版符号一致性检查：
        - 提取 $...$ 中的变量定义模式
        - 检查同一缩写是否在不同位置有不同含义
        """
        # 收集所有缩写定义
        # 模式: "Full Name (ABBREVIATION)" 或 "ABBREVIATION (Full Name)"
        pattern1 = re.compile(r'\b([A-Z]{2,6})\b\s*[\(（]([^)）]{5,50})[\)）]')
        pattern2 = re.compile(r'[\(（]([^)）]{5,50})[\)）]\s*\b([A-Z]{2,6})\b')

        abbrev_map: Dict[str, List[str]] = {}

        for key, content in chapters.items():
            if not isinstance(content, str):
                continue
            for m in pattern1.finditer(content):
                abbrev, full = m.group(1), m.group(2).strip()
                if abbrev not in abbrev_map:
                    abbrev_map[abbrev] = []
                if full not in abbrev_map[abbrev]:
                    abbrev_map[abbrev].append(full)

            for m in pattern2.finditer(content):
                full, abbrev = m.group(1).strip(), m.group(2)
                if abbrev not in abbrev_map:
                    abbrev_map[abbrev] = []
                if full not in abbrev_map[abbrev]:
                    abbrev_map[abbrev].append(full)

        # 找出有多个不同含义的缩写
        ambiguous = {
            k: v for k, v in abbrev_map.items()
            if len(v) > 1
        }

        if not ambiguous:
            return {"passed": True, "score": 100, "details": "缩写一致性检查通过"}

        details = "; ".join(
            f"{k} 有 {len(v)} 个定义: {v[:2]}" for k, v in ambiguous.items()
        )
        score = max(0, 100 - len(ambiguous) * 10)

        return {
            "passed": len(ambiguous) <= 2,
            "score": score,
            "severity": "warning",
            "details": details,
            "fix_hint": "统一全文中同一缩写的含义，或在首次使用时明确定义",
        }

    # ──────────── 单章节验证 ────────────

    def verify_chapter(self, chapter_name: str, content: str,
                       previous_content: str = "") -> VerifyReport:
        """
        对单个章节进行验证（章节生成后即时调用）

        Args:
            chapter_name: 章节名称
            content: 章节内容
            previous_content: 前序章节内容（可选）

        Returns:
            VerifyReport
        """
        report = VerifyReport()

        if not content:
            report.add_check("content_exists", False, 0,
                             details=f"{chapter_name} 内容为空")
            return report

        # 公式语法检查
        formula_result = self._check_formula_syntax(content)
        report.add_check("formula_syntax", **{
            k: formula_result[k] for k in ("passed", "score", "details", "fix_hint")
            if k in formula_result
        })

        # 残留标记检查
        marker_result = self._check_residual_markers(content)
        report.add_check("residual_markers", **{
            k: marker_result[k] for k in ("passed", "score", "details", "fix_hint")
            if k in marker_result
        })

        # 最小长度检查
        word_count = len(content.split())
        min_words = 200  # 每个章节至少200词
        length_ok = word_count >= min_words
        report.add_check(
            "minimum_length",
            passed=length_ok,
            score=min(100, word_count / min_words * 100) if not length_ok else 100,
            details=f"字数: {word_count}（最低要求: {min_words}）",
            fix_hint="扩充章节内容" if not length_ok else "",
        )

        # 有无标题
        has_heading = bool(re.search(r'^#{1,3}\s+\S+', content, re.MULTILINE))
        report.add_check(
            "has_heading",
            passed=True,  # 有标题加分，没有也不算失败
            score=100 if has_heading else 50,
            severity="warning",
            details="有章节标题" if has_heading else "无章节标题",
        )

        logger.info(f"[VERIFY] {chapter_name}: {report.summary()}")
        return report
