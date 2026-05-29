# -*- coding: utf-8 -*-
"""CVPR — IEEE/CVF 顶会配置

调研回顾 (CVPR 2026):
- 页数: 正文8页 (不含参考文献), 参考文献+appendix 附加页
- 格式: CVPR style (cvpr LaTeX class), double-blind review
- 投稿量: ~20,000 submissions (CVPR 2026)
- 关键: 第一印象决定性 — novelty 要在 abstract 和 intro 前几段凸显
- reviewer 看重: 技术创新性 + 视觉效果 + 紧凑实验
- 与 TIP/TPAMI 区别: 8页紧凑格式, 不需 exhaustive ablation,
  但需要 clear contribution + compelling visual results
"""

from config.venue_profiles.base_profile import (
    VenueProfile, SectionBudget, FigureRequirement, AblationConfig,
)


class CVPR_Profile(VenueProfile):
    venue_name = "IEEE/CVF Conference on Computer Vision and Pattern Recognition"
    venue_type = "conference"
    venue_tier = "top_conference"

    max_pages = 8
    abstract_words = 200
    abstract_max_words = 250

    citation_style = "numeric"
    figure_style = "column_width"
    latex_class = "cvpr"

    sections = [
        "Introduction", "Related Work", "Methodology",
        "Experiments", "Conclusion",
    ]
    extra_sections = []  # 会议论文不需要额外章节

    ablation = AblationConfig(
        min_ablations=2,
        max_ablations=3,
        expected_datasets=2,
        needs_computational_analysis=False,
        needs_failure_analysis=False,
        needs_cross_dataset=False,
        needs_statistical_analysis=False,
        result_table_format="latex_three_line",
    )

    figure_requirements = [
        FigureRequirement("teaser", True, 1, 1, "page_width", "full"),
        FigureRequirement("architecture", True, 1, 1, "page_width", "full"),
        FigureRequirement("comparison", True, 1, 2, "column_width", "moderate"),
        FigureRequirement("ablation", True, 1, 2, "column_width", "minimal"),
        FigureRequirement("qualitative", False, 0, 1, "page_width", "moderate"),
    ]

    section_budgets = [
        SectionBudget("Introduction", 500, 350, 700, "core",
                      ["Motivation", "Contributions"]),
        SectionBudget("Related Work", 350, 200, 500, "core",
                      ["Most Relevant"]),
        SectionBudget("Methodology", 1500, 1100, 2000, "core",
                      ["Overview", "Key Module"]),
        SectionBudget("Experiments", 1000, 700, 1400, "core",
                      ["Setup", "Main Results", "Ablation"]),
        SectionBudget("Conclusion", 250, 150, 400, "core"),
    ]

    prohibited_terms = [
        "curriculum learning", "pedagogical",
    ]
    preferred_terms = {
        "curriculum learning": "progressive training / staged training",
        "student-teacher": "knowledge distillation / guided training",
    }
    writing_style = {
        "tone": "formal and impactful, emphasize novelty and visual appeal",
        "argument_depth": "moderate — focus on key insights and innovations",
        "novelty_emphasis": "strong — highlight novelty early and often, first impression matters",
        "experiment_rigor": "solid — main comparisons + compact ablations",
        "related_work_depth": "concise — focused on most relevant, one paragraph is common",
        "methodology_depth": "moderate — key formulations + architecture diagram",
    }

    quality_pass_threshold = 70.0
    num_reviewers = 1
    needs_seven_anchor_test = False
    needs_closed_book_rewrite = False
