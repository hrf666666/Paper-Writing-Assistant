# -*- coding: utf-8 -*-
"""IEEE Transactions on Circuits and Systems for Video Technology (TCSVT) — 顶刊配置

调研回顾 (2026):
- IEEE Circuits and Systems Society 出版
- 范围: 所有视频技术的电路和系统方面
  - 图像/视频获取、表示、压缩、编码
  - 视频理解、目标检测、跟踪、分割
  - 深度学习用于视频处理
- 格式: IEEE Transactions two-column, ~12-14页
- 关键特点: 偏向 circuits+systems 视角, 兼收 CV/视频算法论文
  - 与 TIP 的区别: TCSVT 更侧重视频/系统, TIP 侧重图像处理
  - 与 TPAMI 的区别: TCSVT 更偏向视频技术和系统实现
"""

from config.venue_profiles.base_profile import (
    VenueProfile, SectionBudget, FigureRequirement, AblationConfig,
)


class IEEE_TCSVT_Profile(VenueProfile):
    venue_name = "IEEE Transactions on Circuits and Systems for Video Technology"
    venue_type = "journal"
    venue_tier = "top_journal"

    max_pages = 14
    abstract_words = 250
    abstract_max_words = 300

    citation_style = "numeric"
    figure_style = "column_width"
    latex_class = "IEEEtran"

    sections = [
        "Introduction", "Related Work", "Methodology",
        "Experiments", "Conclusion",
    ]
    extra_sections = ["Discussion", "Limitations and Future Work"]

    ablation = AblationConfig(
        min_ablations=4,
        max_ablations=7,
        expected_datasets=3,
        needs_computational_analysis=True,
        needs_failure_analysis=True,
        needs_cross_dataset=True,
        needs_statistical_analysis=False,
        result_table_format="latex_three_line",
    )

    figure_requirements = [
        FigureRequirement("teaser", True, 1, 1, "page_width", "full"),
        FigureRequirement("architecture", True, 1, 2, "page_width", "full"),
        FigureRequirement("comparison", True, 2, 3, "column_width", "full"),
        FigureRequirement("ablation", True, 2, 3, "column_width", "moderate"),
        FigureRequirement("qualitative", True, 1, 2, "page_width", "full"),
    ]

    section_budgets = [
        SectionBudget("Introduction", 800, 600, 1100, "core"),
        SectionBudget("Related Work", 1000, 700, 1500, "core"),
        SectionBudget("Methodology", 2500, 1800, 3500, "core"),
        SectionBudget("Experiments", 2000, 1500, 2800, "core"),
        SectionBudget("Discussion", 500, 300, 800, "extended"),
        SectionBudget("Limitations and Future Work", 400, 250, 600, "extended"),
        SectionBudget("Conclusion", 500, 350, 700, "core"),
    ]

    prohibited_terms = [
        "curriculum learning", "pedagogical", "teaching", "student-teacher",
    ]
    preferred_terms = {
        "curriculum learning": "progressive training / multi-stage training",
        "student-teacher": "knowledge distillation / guided training",
    }
    writing_style = {
        "tone": "formal and precise, video/systems-oriented",
        "argument_depth": "deep — justify design choices with theoretical or empirical evidence",
        "novelty_emphasis": "explicit — state contributions clearly",
        "experiment_rigor": "extensive — ablations + cross-dataset evaluation",
        "related_work_depth": "thorough — well-categorized",
        "methodology_depth": "detailed — derivations + system overview",
    }

    # ---- v10.1: 内容编排软约束（TCSVT 特有，从已发表论文学习）----
    content_patterns = {
        "Introduction": {
            "opening": "problem_motivation",
            "contributions": "bulleted_3items",
            "has_paper_structure": True,
            # G1: venue 驱动的按章元素配置（替代 ChapterAgent 硬编码）
            "chapter_elements": {"has_figure": False, "has_formula": False, "has_table": False},
        },
        "Related Work": {
            "organization": "by_approach",
            "critique_style": "end_of_group",
            "comparison_depth": "moderate",
            "chapter_elements": {"has_figure": False, "has_formula": False, "has_table": False},
        },
        "Methodology": {
            "starts_with": "overview",
            "derivation_style": "full",
            "has_algorithm_box": False,
            "chapter_elements": {"has_figure": True, "has_formula": True, "has_table": False},
        },
        "Experiments": {
            "dataset_description": "brief_text",
            "ablation_style": "table",
            "comparison_style": "table",
            "has_failure_analysis": True,
            "chapter_elements": {"has_figure": True, "has_formula": False, "has_table": True},
        },
        "Conclusion": {
            "chapter_elements": {"has_figure": False, "has_formula": False, "has_table": False},
        },
    }

    argument_rhythm = {
        "Methodology": {
            "theory_first": True,
            "derivation_depth": "full_for_innovation_brief_for_baseline",
        },
        "Experiments": {
            "data_placement": "after_each_claim",
            "figure_density": "moderate",
        },
    }

    depth_gradients = {
        "Methodology": "full_derivation",
        "Experiments": "comprehensive",
        "Related Work": "moderate",
    }

    figure_preferences = {
        "architecture": {"style": "clean_flowchart", "detail_level": "moderate"},
        "comparison": {"style": "table_heavy", "color_scheme": "muted"},
        "ablation": {"style": "three_line_table", "color_scheme": "blue_dominant"},
    }

    content_emphasis = {
        "methodology": "system_implementation",
        "experiments": "cross_dataset",
    }

    reviewer_preferences = [
        "Always include cross-dataset evaluation",
        "Computational complexity analysis expected",
        "Video/systems perspective valued",
        "Comparison with recent (last 2 years) methods expected",
    ]

    journal_red_flags = [
        "Pure image processing without video/system context",
        "No cross-dataset evaluation",
        "Missing ablation study",
        "Only synthetic data experiments",
        "No computational cost analysis",
    ]

    quality_pass_threshold = 72.0
    num_reviewers = 3
    needs_seven_anchor_test = True
    needs_closed_book_rewrite = True
