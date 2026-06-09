# -*- coding: utf-8 -*-
"""
Venue Profile 基类 — 定义所有期刊/会议场景的配置接口

所有具体 venue 继承此基类，按需覆写属性。
下游所有 skill/agent 通过 VenueAdapter 读取配置，
而非直接 import project_config 中的硬编码字典。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SectionBudget:
    """单个章节的篇幅预算"""
    name: str                # 章节英文名
    target_words: int        # 目标字数
    min_words: int           # 最少字数
    max_words: int           # 最多字数
    priority: str = "core"   # core | optional | extended
    subsections: List[str] = field(default_factory=list)


@dataclass
class FigureRequirement:
    """图表要求"""
    figure_type: str         # "architecture" | "teaser" | "comparison" | "ablation" | "qualitative"
    required: bool = True
    min_count: int = 1
    max_count: int = 2
    style: str = "column_width"  # "column_width" | "page_width" | "double_column"
    caption_detail: str = "full"  # "minimal" | "moderate" | "full"


@dataclass
class AblationConfig:
    """消融实验配置"""
    min_ablations: int = 2
    max_ablations: int = 5
    expected_datasets: int = 2
    needs_computational_analysis: bool = False
    needs_failure_analysis: bool = False
    needs_cross_dataset: bool = False
    needs_statistical_analysis: bool = False
    result_table_format: str = "latex_three_line"  # "latex_three_line" | "latex_full" | "markdown"


class VenueProfile:
    """
    场景配置基类

    子类覆写类属性即可，无需重写方法。
    """

    # ---- 基本信息 ----
    venue_name: str = "Unknown"
    venue_type: str = "journal"  # "journal" | "conference"
    venue_tier: str = "top_journal"  # top_journal | top_conference | good_venue

    # ---- 篇幅限制 ----
    max_pages: int = 14
    abstract_words: int = 250
    abstract_max_words: int = 300

    # ---- 引用 / 排版 ----
    citation_style: str = "numeric"     # "numeric" | "author_year"
    figure_style: str = "column_width"
    latex_class: str = "IEEEtran"

    # ---- 章节结构 ----
    sections: List[str] = field(default_factory=lambda: [
        "Introduction", "Related Work", "Methodology",
        "Experiments", "Conclusion"
    ])
    extra_sections: List[str] = field(default_factory=list)

    # ---- 消融实验 ----
    ablation: AblationConfig = field(default_factory=AblationConfig)

    # ---- 图表要求 ----
    figure_requirements: List[FigureRequirement] = field(default_factory=list)

    # ---- 章节篇幅预算 ----
    section_budgets: List[SectionBudget] = field(default_factory=list)

    # ---- 术语约束 ----
    prohibited_terms: List[str] = field(default_factory=list)
    preferred_terms: Dict[str, str] = field(default_factory=dict)

    # ---- 写作风格 ----
    writing_style: Dict[str, str] = field(default_factory=dict)

    # ---- v10.1: 内容编排软约束（从 ref_pdf 学习填充）----
    # 期刊特有的内容编排模式（由 JournalStyleLearner 从 ref_pdf 填充）
    content_patterns: Dict[str, Any] = field(default_factory=dict)
    # 例: {"Introduction": {"opening": "problem_motivation", "contributions": "bulleted_3items"}}

    # 论证节奏（哪里放数据/图表/引用，哪里详写/略写）
    argument_rhythm: Dict[str, Any] = field(default_factory=dict)
    # 例: {"Methodology": {"theory_first": True, "derivation_depth": "full"}}

    # 深度梯度（每个子节的推导深度）
    depth_gradients: Dict[str, str] = field(default_factory=dict)
    # 例: {"Methodology.3.1": "full_derivation", "Methodology.3.2": "overview"}

    # 图片风格偏好（从该期刊论文中学习的图表风格）
    figure_preferences: Dict[str, Any] = field(default_factory=dict)
    # 例: {"architecture": {"style": "clean_lines", "detail_level": "moderate"}}

    # 期刊特有的内容侧重点（该期刊更看重什么）
    content_emphasis: Dict[str, str] = field(default_factory=dict)
    # 例: {"methodology": "system_implementation", "experiments": "cross_dataset"}

    # 审稿偏好（该期刊审稿人通常关注的点）
    reviewer_preferences: List[str] = field(default_factory=list)
    # 例: ["always include complexity analysis", "prefer real-world datasets"]

    # 期刊特有的 Red Flags（该期刊明确不欢迎的写作模式）
    journal_red_flags: List[str] = field(default_factory=list)

    # ---- 质量门控 ----
    quality_pass_threshold: float = 70.0
    quality_max_retries: int = 3

    # ---- 审阅配置 ----
    num_reviewers: int = 1          # 多代理审阅人数
    needs_seven_anchor_test: bool = False
    needs_closed_book_rewrite: bool = False

    def get_section_budget(self, section_name: str) -> Optional[SectionBudget]:
        """获取指定章节的篇幅预算"""
        for budget in self.section_budgets:
            if budget.name.lower() == section_name.lower():
                return budget
        return None

    def get_figure_requirement(self, figure_type: str) -> Optional[FigureRequirement]:
        """获取指定类型图表的要求"""
        for req in self.figure_requirements:
            if req.figure_type == figure_type:
                return req
        return None

    def get_full_sections(self) -> List[str]:
        """获取完整章节列表（含额外章节）"""
        return self.sections + self.extra_sections

    def to_prompt_block(self) -> str:
        """生成用于 LLM prompt 的配置块"""
        lines = [
            f"**目标Venue**: {self.venue_name} ({self.venue_type}, {self.venue_tier})",
            f"**篇幅限制**: 最大 {self.max_pages} 页",
            f"**摘要字数**: {self.abstract_words} 词 (最大 {self.abstract_max_words})",
            f"**引用风格**: {self.citation_style}",
        ]

        if self.extra_sections:
            lines.append(f"**额外章节**: {', '.join(self.extra_sections)}")

        if self.ablation.min_ablations > 0:
            lines.append(
                f"**消融实验**: {self.ablation.min_ablations}-{self.ablation.max_ablations} 个, "
                f"数据集 {self.ablation.expected_datasets}+"
            )

        if self.writing_style:
            lines.append("**写作风格**:")
            for key, desc in self.writing_style.items():
                lines.append(f"  - {key}: {desc}")

        return "\n".join(lines)
