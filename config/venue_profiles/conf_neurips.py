# -*- coding: utf-8 -*-
"""NeurIPS — 顶会配置"""

from config.venue_profiles.base_profile import (
    VenueProfile, SectionBudget, FigureRequirement, AblationConfig,
)


class NeurIPS_Profile(VenueProfile):
    venue_name = "Conference on Neural Information Processing Systems"
    venue_type = "conference"
    venue_tier = "top_conference"

    max_pages = 10
    abstract_words = 250
    abstract_max_words = 300

    citation_style = "numeric"
    figure_style = "column_width"
    latex_class = "neurips"

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
        FigureRequirement("ablation", True, 1, 2, "column_width", "moderate"),
        FigureRequirement("qualitative", False, 0, 2, "page_width", "moderate"),
    ]

    section_budgets = [
        SectionBudget("Introduction", 600, 400, 800, "core"),
        SectionBudget("Related Work", 400, 250, 600, "core"),
        SectionBudget("Methodology", 1800, 1200, 2500, "core"),
        SectionBudget("Experiments", 1200, 800, 1600, "core"),
        SectionBudget("Conclusion", 300, 200, 450, "core"),
    ]

    prohibited_terms = [
        "curriculum learning", "pedagogical",
    ]
    preferred_terms = {
        "curriculum learning": "progressive training / staged training",
        "student-teacher": "knowledge distillation / guided training",
    }
    writing_style = {
        "tone": "formal, theory-grounded, emphasize insight and elegance",
        "argument_depth": "moderate-to-deep — justify key design with intuition and evidence",
        "novelty_emphasis": "strong — highlight what is fundamentally new",
        "experiment_rigor": "solid — clean comparisons + targeted ablations",
        "related_work_depth": "concise — focused on positioning",
        "methodology_depth": "moderate-to-detailed — emphasize theoretical elegance",
    }

    quality_pass_threshold = 72.0
    num_reviewers = 2
    needs_seven_anchor_test = False
    needs_closed_book_rewrite = False
