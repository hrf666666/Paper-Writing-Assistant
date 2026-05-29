# -*- coding: utf-8 -*-
"""ICCV — IEEE/CVF 顶会配置

调研回顾 (ICCV 2025/2026):
- 页数: 正文8页 (不含参考文献), 参考文献不限页数
- 格式: ICCV style (基于 CVPR style), double-blind review
- 周期: 双年举办 (奇数年: ICCV, 偶数年: ECCV)
- 投稿: ~8,000-10,000 submissions
- 审稿标准与 CVPR 类似, 但偏重技术深度
- abstract 最大 4000 字符
- 关键: supplementary 必须与正文分开提交, 否则 desk reject
- reviewer 要求: fair, thoughtful, detailed; 禁止一句话 review
"""

from config.venue_profiles.base_profile import (
    VenueProfile, SectionBudget, FigureRequirement, AblationConfig,
)


class ICCV_Profile(VenueProfile):
    venue_name = "IEEE/CVF International Conference on Computer Vision"
    venue_type = "conference"
    venue_tier = "top_conference"

    max_pages = 8
    abstract_words = 200
    abstract_max_words = 250

    citation_style = "numeric"
    figure_style = "column_width"
    latex_class = "iccv"

    sections = [
        "Introduction", "Related Work", "Methodology",
        "Experiments", "Conclusion",
    ]
    extra_sections = []

    ablation = AblationConfig(
        min_ablations=2,
        max_ablations=4,
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
        "tone": "formal and impactful, emphasize technical depth and novelty",
        "argument_depth": "moderate-to-deep — focus on key technical insights and methodological innovations",
        "novelty_emphasis": "strong — highlight novelty early and often; ICCV values technical depth slightly more than CVPR",
        "experiment_rigor": "solid — main comparisons + targeted ablations; supplementary for extended results",
        "related_work_depth": "concise — focused on most relevant work, one paragraph is common",
        "methodology_depth": "moderate-to-detailed — key formulations + architecture diagram; full derivations can go to supplementary",
        "supplementary_usage": "encouraged — put extended proofs, additional experiments, and qualitative results in supplementary",
    }

    quality_pass_threshold = 72.0
    num_reviewers = 2
    needs_seven_anchor_test = False
    needs_closed_book_rewrite = False
