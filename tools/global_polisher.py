# -*- coding: utf-8 -*-
"""
Tool: 全局打磨器

在所有章节完成、引用解析之后执行。通读全文，5 维度全局优化：
1. 跨章节过渡 — 检查每章结尾和下一章开头的过渡
2. 术语统一 — 同一概念全文用同一术语
3. 符号统一 — 数学符号全文一致
4. 冗余消除 — 跨章节重复表述改为交叉引用
5. 节奏优化 — 篇幅均匀性
"""

import os
import re
import json
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class GlobalPolisher:
    """全局打磨器"""

    def __init__(self, output_dir: str, api_client=None):
        self.output_dir = output_dir
        self.api_client = api_client

    def polish(self, chapters: Dict, abstract: str = "",
               anchor_map: Dict = None) -> Dict:
        """
        全局打磨

        Args:
            chapters: {1: "Introduction text", 2: "RW text", ...}
            abstract: 摘要文本
            anchor_map: 创新点锚定映射

        Returns:
            {
                "polished_chapters": {1: "...", 2: "...", ...},
                "changes": [...],
                "quality_delta": +3.5,
            }
        """
        changes = []

        # 1. 术语统一（纯规则，零 LLM 成本）
        chapters, term_changes = self._unify_terminology(chapters)
        changes.extend(term_changes)

        # 2. 符号统一（纯规则）
        chapters, symbol_changes = self._unify_symbols(chapters)
        changes.extend(symbol_changes)

        # 3. 跨章节过渡增强（LLM）
        if self.api_client and len(chapters) >= 2:
            chapters, transition_changes = self._enhance_transitions(chapters)
            changes.extend(transition_changes)

        # 4. 冗余消除（纯规则）
        chapters, dedup_changes = self._eliminate_redundancy(chapters)
        changes.extend(dedup_changes)

        # 5. 节奏检查（纯规则，不修改内容）
        rhythm_report = self._check_rhythm(chapters)

        # 摘要与正文一致性检查
        if abstract and self.api_client:
            chapters, abs_changes = self._align_abstract_data(chapters, abstract)
            changes.extend(abs_changes)

        quality_delta = min(len(changes) * 0.5, 10.0)

        result = {
            "polished_chapters": chapters,
            "changes": changes,
            "quality_delta": quality_delta,
            "rhythm_report": rhythm_report,
            "total_changes": len(changes),
        }

        # 保存报告
        report_path = os.path.join(self.output_dir, "global_polish_report.json")
        report = {k: v for k, v in result.items() if k != "polished_chapters"}
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"[GlobalPolish] 完成: {len(changes)} 处修改, "
                     f"预估质量提升 +{quality_delta:.1f}")
        return result

    def _unify_terminology(self, chapters: Dict) -> Tuple[Dict, List]:
        """术语统一"""
        changes = []
        term_mappings = {
            # 统一为标准术语
            "light-field": "light field",
            "Lightfield": "light field",
            "light field depth": "light field depth",
            "depth map": "depth map",
            "depth estimation": "depth estimation",
            "non-lambertian": "non-Lambertian",
            "Non-Lambertian": "non-Lambertian",
            "non_lambertian": "non-Lambertian",
            "epipolar plane image": "epipolar plane image (EPI)",
            "EPI method": "EPI-based method",
        }

        for ch_num, content in chapters.items():
            original = content
            for old, new in term_mappings.items():
                # 只替换独立出现的（不在已有正确形式中）
                if old in content and new not in content[:content.index(old)]:
                    content = content.replace(old, new)

            if content != original:
                diff_count = sum(1 for a, b in zip(original.split(), content.split())
                                 if a != b)
                if diff_count > 0:
                    changes.append({
                        "type": "terminology",
                        "chapter": ch_num,
                        "count": diff_count,
                        "description": f"统一术语 {diff_count} 处",
                    })
                chapters[ch_num] = content

        return chapters, changes

    def _unify_symbols(self, chapters: Dict) -> Tuple[Dict, List]:
        """符号统一"""
        changes = []
        # 检查常见符号不一致
        symbol_patterns = [
            # (pattern, standard_form, description)
            (r'\bMAE\b', "MAE", "MAE 指标"),
            (r'\bRMSE\b', "RMSE", "RMSE 指标"),
            (r'\bBRDF\b', "BRDF", "BRDF"),
            (r'\bEPI\b', "EPI", "EPI"),
            (r'\bRTF\b', "RTF", "RTF"),
            (r'\bDFT\b', "DFT", "DFT"),
            (r'\b2D-DFT\b', "2D-DFT", "2D-DFT"),
        ]

        for ch_num, content in chapters.items():
            modified = False
            for pattern, standard, desc in symbol_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    non_standard = [m for m in matches if m != standard]
                    if non_standard:
                        content = re.sub(pattern, standard, content)
                        modified = True

            if modified:
                changes.append({
                    "type": "symbol",
                    "chapter": ch_num,
                    "description": "符号统一",
                })
                chapters[ch_num] = content

        return chapters, changes

    def _enhance_transitions(self, chapters: Dict) -> Tuple[Dict, List]:
        """跨章节过渡增强"""
        changes = []
        chapter_names = {
            1: "Introduction", 2: "Related Work", 3: "Methodology",
            4: "Experiments", 5: "Conclusion",
        }

        for ch_num in sorted(chapters.keys(), key=lambda x: str(x)):
            next_num = ch_num + 1
            if next_num not in chapters:
                continue
            if ch_num not in chapter_names or next_num not in chapter_names:
                continue

            current = chapters[ch_num]
            next_ch = chapters[next_num]

            # 检查当前章最后一段是否有过渡句
            last_para = current.strip().split("\n\n")[-1] if "\n\n" in current else current.strip()[-200:]
            has_transition = any(kw in last_para.lower() for kw in [
                "in the next", "following section", "next, we", "section",
                "接下来", "下一节", "subsequent",
            ])

            if not has_transition:
                # LLM 生成过渡句
                prompt = f"""Add a 1-sentence transition at the end of {chapter_names[ch_num]} to connect to {chapter_names[next_num]}.

Last paragraph of {chapter_names[ch_num]}:
{last_para[-300:]}

First paragraph of {chapter_names[next_num]}:
{next_ch[:300]}

Output ONLY the transition sentence, nothing else:"""

                try:
                    transition = self.api_client.call_light(prompt).strip()
                    if transition and len(transition) < 200:
                        # 在当前章节末尾添加过渡句
                        if current.strip().endswith("."):
                            chapters[ch_num] = current.rstrip() + " " + transition + "\n"
                        else:
                            chapters[ch_num] = current.rstrip() + "\n\n" + transition + "\n"
                        changes.append({
                            "type": "transition",
                            "from": chapter_names[ch_num],
                            "to": chapter_names[next_num],
                            "transition": transition[:100],
                        })
                except Exception as e:
                    logger.debug(f"过渡生成失败 ({ch_num}→{next_num}): {e}")

        return chapters, changes

    def _eliminate_redundancy(self, chapters: Dict) -> Tuple[Dict, List]:
        """跨章节冗余消除"""
        changes = []

        # 提取每章的前 200 字作为指纹
        fingerprints = {}
        for ch_num, content in chapters.items():
            sentences = re.split(r'(?<=[.!?])\s+', content[:2000])
            fingerprints[ch_num] = [s.lower().strip() for s in sentences if len(s) > 30]

        # 检查跨章重复
        checked = set()
        for ch_a, sents_a in fingerprints.items():
            for ch_b, sents_b in fingerprints.items():
                if ch_a >= ch_b:
                    continue
                pair = (ch_a, ch_b)
                if pair in checked:
                    continue
                checked.add(pair)

                for sa in sents_a:
                    for sb in sents_b:
                        # Jaccard 相似度
                        words_a = set(sa.split())
                        words_b = set(sb.split())
                        if not words_a or not words_b:
                            continue
                        jaccard = len(words_a & words_b) / len(words_a | words_b)
                        if jaccard > 0.6:
                            changes.append({
                                "type": "redundancy",
                                "chapters": [ch_a, ch_b],
                                "similarity": round(jaccard, 2),
                                "text_a": sa[:80],
                                "text_b": sb[:80],
                                "action": "建议修改其中一处为交叉引用",
                            })

        return chapters, changes

    def _check_rhythm(self, chapters: Dict) -> Dict:
        """节奏检查（篇幅均匀性）"""
        chapter_names = {
            1: "Introduction", 2: "Related Work", 3: "Methodology",
            4: "Experiments", 5: "Conclusion",
        }
        report = {}
        word_counts = {}

        for ch_num, content in chapters.items():
            words = len(content.split())
            name = chapter_names.get(ch_num, f"Chapter {ch_num}")
            word_counts[name] = words

        total = sum(word_counts.values())
        if total == 0:
            return {"status": "no_content"}

        for name, count in word_counts.items():
            pct = count / total * 100
            report[name] = {
                "words": count,
                "percentage": round(pct, 1),
                "status": "ok" if 10 <= pct <= 40 else "too_short" if pct < 10 else "too_long",
            }

        return report

    def _align_abstract_data(self, chapters: Dict, abstract: str) -> Tuple[Dict, List]:
        """摘要与正文数据对齐"""
        changes = []

        # 从 Experiments 提取关键数字
        exp_content = chapters.get(4, "")
        if not exp_content:
            return chapters, changes

        # 提取 MAE 数值
        mae_matches = re.findall(r'(?:MAE|mean absolute error)[:\s=]+(\d+\.\d+)',
                                  exp_content, re.IGNORECASE)
        abs_mae_matches = re.findall(r'(?:MAE|mean absolute error)[:\s=]+(\d+\.\d+)',
                                      abstract, re.IGNORECASE)

        if mae_matches and abs_mae_matches:
            exp_mae = mae_matches[0]
            abs_mae = abs_mae_matches[0]
            if exp_mae != abs_mae:
                changes.append({
                    "type": "data_alignment",
                    "issue": f"Abstract MAE={abs_mae} vs Experiments MAE={exp_mae}",
                    "action": "建议统一为 Experiments 中的数值",
                })

        return chapters, changes


def run_global_polisher(output_dir: str, chapters: Dict, abstract: str = "",
                         api_client=None) -> Dict:
    """全局打磨入口"""
    polisher = GlobalPolisher(output_dir, api_client)
    return polisher.polish(chapters, abstract)
