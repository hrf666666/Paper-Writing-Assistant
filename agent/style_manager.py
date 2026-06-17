# -*- coding: utf-8 -*-
"""
StyleManager — 统一风格管理中心 (v10.1)

为每章生成器提供一站式的风格指导，整合：
1. 期刊级内容编排模式（从 JournalStyleLearner / venue_profile 获取）
2. 期刊级论证节奏和深度梯度
3. 期刊级内容侧重点
4. 通用学术写作规范（从 style_guide.md 获取）
5. 参考论文风格（从 ref_pdf 学到的）
6. 期刊特有的 Red Flags

下游章节生成器不再各自 _build_style_instruction()，统一从此处获取。
"""

from __future__ import annotations

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 引导文件路径
_SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "skills", "academic_writing_style")

# 期刊风格引导模板
_JOURNAL_STYLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "skills", "journal_style")


class StyleManager:
    """统一的风格管理中心"""

    def __init__(
        self,
        venue_adapter=None,
        journal_style_profile: Optional[Dict] = None,
        ref_style_guide: Optional[Dict] = None,
        ieee_trans_profile: Optional[Dict] = None,
    ):
        """
        Args:
            venue_adapter: VenueAdapter 实例（提供硬约束参数）
            journal_style_profile: JournalStyleLearner 的输出（从 ref_pdf 学习的软约束）
            ref_style_guide: ref_pdf_analyzer 的 style_guide 输出
            ieee_trans_profile: ieee_trans_style_profile 的配置（P2 规则）
        """
        self.venue_adapter = venue_adapter
        self.journal_style = journal_style_profile or {}
        self.ref_style = ref_style_guide or {}
        self.ieee_profile = ieee_trans_profile or {}

    def build_chapter_style_instruction(
        self,
        chapter_name: str,
        content_strategy: Optional[Dict] = None,
    ) -> str:
        """
        为指定章节构建完整的风格指导。

        Args:
            chapter_name: 章节英文名（如 "Introduction", "Methodology"）
            content_strategy: ContentStrategist 为该章节生成的策略

        Returns:
            完整的风格指导文本，直接注入到 LLM prompt
        """
        blocks = []

        # 1. 期刊级内容编排模式
        content_pattern = self._get_content_pattern(chapter_name)
        if content_pattern:
            blocks.append(f"**{chapter_name} 内容编排模式**（从目标期刊论文学习）:")
            blocks.append(self._format_content_pattern(content_pattern))

        # 2. 论证节奏
        rhythm = self._get_argument_rhythm(chapter_name)
        if rhythm:
            blocks.append(f"**论证节奏**:")
            blocks.append(self._format_rhythm(rhythm))

        # 3. 深度梯度
        depth = self._get_depth_gradient(chapter_name)
        if depth:
            blocks.append(f"**深度要求**: {depth}")

        # 4. 内容侧重点
        emphasis = self._get_content_emphasis(chapter_name)
        if emphasis:
            blocks.append(f"**内容侧重点**: {emphasis}")

        # 5. 通用学术写作规范
        academic_rules = self._get_academic_rules(chapter_name)
        if academic_rules:
            blocks.append(f"**通用学术写作规范**:")
            blocks.append(academic_rules)

        # 6. 参考论文风格
        ref_style_block = self._get_ref_style_block(chapter_name)
        if ref_style_block:
            blocks.append(f"**参考论文风格**（从 ref_pdf 学习）:")
            blocks.append(ref_style_block)

        # 7. 期刊特有 Red Flags
        red_flags = self._get_red_flags(chapter_name)
        if red_flags:
            blocks.append(f"**Red Flags**（以下模式在本期刊不可接受）:")
            for rf in red_flags:
                blocks.append(f"  - {rf}")

        # 8. 内容策略（如果有）
        if content_strategy:
            blocks.append(self._format_content_strategy(content_strategy))

        if not blocks:
            return self._build_fallback_instruction(chapter_name)

        return "\n".join(blocks)

    # ── 私有方法：各风格维度的提取 ──

    def _get_content_pattern(self, chapter_name: str) -> Dict:
        """获取期刊特有的内容编排模式"""
        # 优先从 JournalStyleLearner 的输出获取
        if self.journal_style:
            patterns = self.journal_style.get("content_patterns", {})
            if chapter_name in patterns:
                return patterns[chapter_name]
            # 尝试小写匹配
            for k, v in patterns.items():
                if k.lower() == chapter_name.lower():
                    return v

        # 降级：从 venue_profile 获取
        if self.venue_adapter:
            profile = getattr(self.venue_adapter, 'profile', None)
            if profile and hasattr(profile, 'content_patterns'):
                patterns = profile.content_patterns
                return patterns.get(chapter_name, patterns.get(chapter_name.lower(), {}))

        return {}

    def _get_argument_rhythm(self, chapter_name: str) -> Dict:
        """获取论证节奏"""
        if self.journal_style:
            rhythms = self.journal_style.get("argument_rhythm", {})
            if chapter_name in rhythms:
                return rhythms[chapter_name]

        if self.venue_adapter:
            profile = getattr(self.venue_adapter, 'profile', None)
            if profile and hasattr(profile, 'argument_rhythm'):
                rhythms = profile.argument_rhythm
                return rhythms.get(chapter_name, {})

        return {}

    def _get_depth_gradient(self, chapter_name: str) -> str:
        """获取深度梯度"""
        if self.journal_style:
            gradients = self.journal_style.get("depth_gradients", {})
            if chapter_name in gradients:
                return gradients[chapter_name]

        if self.venue_adapter:
            profile = getattr(self.venue_adapter, 'profile', None)
            if profile and hasattr(profile, 'depth_gradients'):
                return profile.depth_gradients.get(chapter_name, "")

            # 降级：从 writing_style 推断
            ws = getattr(profile, 'writing_style', {})
            if chapter_name == "Methodology":
                return ws.get("methodology_depth", "")
            elif chapter_name == "Experiments":
                return ws.get("experiment_rigor", "")
            elif chapter_name == "Related Work":
                return ws.get("related_work_depth", "")

        return ""

    def _get_content_emphasis(self, chapter_name: str) -> str:
        """获取内容侧重点"""
        if self.journal_style:
            emphasis = self.journal_style.get("content_emphasis", {})
            if chapter_name in emphasis:
                return emphasis[chapter_name]

        if self.venue_adapter:
            profile = getattr(self.venue_adapter, 'profile', None)
            if profile and hasattr(profile, 'content_emphasis'):
                return profile.content_emphasis.get(chapter_name, "")

        return ""

    def _get_academic_rules(self, chapter_name: str) -> str:
        """
        获取通用学术写作规范

        优先级链：writing_discipline.md (P0) → style_guide.md (P3) → 章节特定规则 → IEEE Trans 规则
        """
        sections = []

        # P0: 通用写作纪律（跨期刊通用，最高优先级）
        discipline_path = os.path.join(_SKILLS_DIR, "writing_discipline.md")
        if os.path.exists(discipline_path):
            try:
                with open(discipline_path, "r", encoding="utf-8") as f:
                    discipline = f.read()
                # 截取核心内容（前3000字符，覆盖信息密度/逻辑衔接/tone/禁用词）
                if discipline:
                    sections.append(f"**Universal Writing Discipline** (P0, mandatory):\n{discipline[:3000]}")
            except Exception:
                pass

        # P3: IEEE 特有学术规范（从 style_guide.md 加载章节相关的规则）
        guide_path = os.path.join(_SKILLS_DIR, "style_guide.md")
        if os.path.exists(guide_path):
            try:
                with open(guide_path, "r", encoding="utf-8") as f:
                    guide = f.read()

                # 截取关键部分（避免太长）
                # 禁用词表
                if "禁止" in guide or "Banned" in guide:
                    idx = guide.find("禁止")
                    if idx == -1:
                        idx = guide.find("Banned")
                    if idx != -1:
                        sections.append(f"**IEEE-Specific Lexical Rules** (P3):\n{guide[idx:idx + 1500]}")

                # P5 清理规则
                if "P5" in guide:
                    idx = guide.find("P5")
                    if idx != -1:
                        sections.append(guide[idx:idx + 1000])

                # 章节特定规则（从 style_guide.md 第5节提取）
                chapter_section_map = {
                    "Introduction": "5.1 Introduction",
                    "Related Work": "5.2 Related Work",
                    "Methodology": "5.3 Methodology",
                    "Experiments": "5.4 Experiments",
                    "Conclusion": "5.5 Conclusion",
                }
                section_header = chapter_section_map.get(chapter_name)
                if section_header and section_header in guide:
                    start = guide.find(section_header)
                    # 找到下一个同级标题或文件末尾
                    next_section = guide.find("\n### 5.", start + len(section_header))
                    if next_section == -1:
                        next_section = guide.find("\n## 6.", start)
                    end = next_section if next_section != -1 and next_section > start else start + 1000
                    sections.append(guide[start:end])
            except Exception:
                pass

        # 章节特定规则（硬编码兜底）
        chapter_rules = self._get_chapter_specific_rules(chapter_name)
        if chapter_rules:
            sections.append(chapter_rules)

        # IEEE Trans 规则（如果有的话）
        if self.ieee_profile:
            chapter_conventions = self.ieee_profile.get(
                "introduction_conventions" if chapter_name == "Introduction"
                else "literature_review_norms" if chapter_name == "Related Work"
                else "methodology_norms" if chapter_name == "Methodology"
                else "experiment_norms" if chapter_name == "Experiments"
                else "conclusion_norms",
                None
            )
            if chapter_conventions:
                if isinstance(chapter_conventions, list):
                    sections.append("\n".join(
                        f"  - {c.get('pattern', c) if isinstance(c, dict) else c}"
                        for c in chapter_conventions
                    ))

        return "\n\n".join(sections) if sections else ""

    def _get_chapter_specific_rules(self, chapter_name: str) -> str:
        """硬编码的章节特定规则（兜底）"""
        rules = {
            "Introduction": (
                "  - 开篇陈述问题动机（不要以领域历史开头）\n"
                "  - 明确现有方法的局限性后再介绍本文方法\n"
                "  - 贡献以列表呈现，2-3 项，每项是具体可验证的声明\n"
                "  - 贡献用事实语气（'We propose X that achieves Y'），不用意图语气\n"
                "  - 末尾包含论文组织结构"
            ),
            "Related Work": (
                "  - 按方法/技术分类，不按时间顺序\n"
                "  - 每篇工作用 1-2 段描述\n"
                "  - 每个小节末尾集中讨论该类方法的不足\n"
                "  - 引用自然融入句式\n"
                "  - 对比要有明确的差异化（不只是罗列）"
            ),
            "Methodology": (
                "  - 每个模块先说设计动机，再说具体设计，最后说预期效果\n"
                "  - 公式完整，每个符号都要定义\n"
                "  - 模块间关系和数据流清晰\n"
                "  - 创新点自然突出（'different from previous works that..., our module explicitly...'）"
            ),
            "Experiments": (
                "  - 数据集描述详细但简洁\n"
                "  - 对比实验客观，不回避不足\n"
                "  - 消融实验分析深入（不能只说'性能下降了X%'）\n"
                "  - 每个发现关联到方法设计\n"
                "  - 数值结果用具体数字，不用模糊表述"
            ),
            "Conclusion": (
                "  - 总结核心贡献和创新\n"
                "  - 与 Introduction 的贡献列表呼应\n"
                "  - 提出具体的未来方向\n"
                "  - 简洁有力，不超过 1 页"
            ),
        }
        return rules.get(chapter_name, "")

    def _get_ref_style_block(self, chapter_name: str) -> str:
        """获取参考论文的风格特征"""
        if not self.ref_style:
            return ""

        blocks = []

        # 句式特征
        patterns = self.ref_style.get("句式特征", {})
        if patterns and isinstance(patterns, dict):
            blocks.append(f"  常用句式: {list(patterns.keys())[:5]}")

        # 用词特征
        vocab = self.ref_style.get("用词特征", [])
        if vocab:
            blocks.append(f"  学术用词: {vocab[:15]}")

        # 引用风格
        cite = self.ref_style.get("引用风格", {})
        if cite:
            blocks.append(f"  引用风格: {cite}")

        return "\n".join(blocks)

    def _get_red_flags(self, chapter_name: str) -> list:
        """获取期刊特有的 Red Flags"""
        # 期刊级 red flags
        if self.journal_style:
            rfs = self.journal_style.get("journal_red_flags", [])
            if rfs:
                return rfs

        # venue_profile 级
        if self.venue_adapter:
            profile = getattr(self.venue_adapter, 'profile', None)
            if profile and hasattr(profile, 'journal_red_flags'):
                return profile.journal_red_flags

        # 通用 IEEE Trans red flags
        if self.ieee_profile:
            return self.ieee_profile.get("red_flags", [])

        return []

    # ── 格式化方法 ──

    def _format_content_pattern(self, pattern: Dict) -> str:
        """格式化内容编排模式"""
        if not pattern:
            return ""
        lines = []
        for key, value in pattern.items():
            if isinstance(value, list):
                lines.append(f"  - {key}: {', '.join(str(v) for v in value)}")
            elif isinstance(value, dict):
                lines.append(f"  - {key}:")
                for k2, v2 in value.items():
                    lines.append(f"    - {k2}: {v2}")
            else:
                lines.append(f"  - {key}: {value}")
        return "\n".join(lines)

    def _format_rhythm(self, rhythm: Dict) -> str:
        """格式化论证节奏"""
        if not rhythm:
            return ""
        lines = []
        for key, value in rhythm.items():
            lines.append(f"  - {key}: {value}")
        return "\n".join(lines)

    def _format_content_strategy(self, strategy: Dict) -> str:
        """格式化内容策略"""
        blocks = ["**内容策略**（基于创新点和目标期刊规划）:"]

        focus = strategy.get("focus_areas", [])
        if focus:
            blocks.append(f"  重点领域: {', '.join(focus)}")

        depth_map = strategy.get("depth_map", {})
        if depth_map:
            blocks.append("  深度分配:")
            for k, v in depth_map.items():
                blocks.append(f"    - {k}: {v}")

        innovation_alloc = strategy.get("innovation_allocation", {})
        if innovation_alloc:
            blocks.append("  创新点分配:")
            for k, v in innovation_alloc.items():
                blocks.append(f"    - {k}: {v}")

        must_include = strategy.get("must_include", [])
        if must_include:
            blocks.append("  必须覆盖:")
            for item in must_include:
                blocks.append(f"    - {item}")

        should_avoid = strategy.get("should_avoid", [])
        if should_avoid:
            blocks.append("  应当避免:")
            for item in should_avoid:
                blocks.append(f"    - {item}")

        return "\n".join(blocks)

    def _build_fallback_instruction(self, chapter_name: str) -> str:
        """兜底：无法获取任何风格配置时使用"""
        return (
            f"**写作风格指导**（{chapter_name}）:\n"
            f"{self._get_chapter_specific_rules(chapter_name)}\n"
            "- 文风必须学术化，禁止口语化表达\n"
            "- 每句话都要有明确的论述目的\n"
            "- 引用要自然融入句式\n"
        )
