# -*- coding: utf-8 -*-
"""IEEE Transactions on Image Processing (TIP) — 顶刊配置

调研回顾 (2026):
- IF 11+, EIC: Benoit Macq (UCLouvain), IEEE Signal Processing Society
- 格式: ~13页 two-column IEEE Transactions format (10-point)
- OA APC: $2,345, 订阅路线无作者费用
- 审稿周期: 4-7个月首次决定
- Desk rejection 3大触发因素:
  1. 缺乏方法论创新 (纯应用不收)
  2. baseline对比不充分/消融不够
  3. 主题应投专刊 (TMI/TMM/TCI)
- 关键区分: TIP收 image processing 方法论, 不是纯应用;
  与 TPAMI (general CV) 和 TMI (medical) 划清边界
"""

from config.venue_profiles.base_profile import (
    VenueProfile, SectionBudget, FigureRequirement, AblationConfig,
)


class IEEE_TIP_Profile(VenueProfile):
    venue_name = "IEEE Transactions on Image Processing"
    venue_type = "journal"
    venue_tier = "top_journal"

    max_pages = 13
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
        min_ablations=5,
        max_ablations=8,
        expected_datasets=3,
        needs_computational_analysis=True,
        needs_failure_analysis=True,
        needs_cross_dataset=True,
        needs_statistical_analysis=True,
        result_table_format="latex_three_line",
    )

    figure_requirements = [
        FigureRequirement("teaser", True, 1, 1, "page_width", "full"),
        FigureRequirement("architecture", True, 1, 2, "page_width", "full"),
        FigureRequirement("comparison", True, 2, 4, "column_width", "full"),
        FigureRequirement("ablation", True, 2, 3, "column_width", "moderate"),
        FigureRequirement("qualitative", True, 1, 3, "page_width", "full"),
    ]

    section_budgets = [
        SectionBudget("Introduction", 800, 600, 1200, "core",
                      ["Motivation", "Contributions", "Paper Organization"]),
        SectionBudget("Related Work", 1200, 800, 1800, "core",
                      ["Category A", "Category B", "Summary and Gap"]),
        SectionBudget("Methodology", 2500, 1800, 3500, "core",
                      ["Overview", "Module Details", "Loss Function", "Training Strategy"]),
        SectionBudget("Experiments", 2000, 1500, 3000, "core",
                      ["Setup", "Main Results", "Ablation Studies",
                       "Computational Analysis", "Failure Analysis"]),
        SectionBudget("Discussion", 600, 400, 1000, "extended",
                      ["Key Findings", "Broader Impact"]),
        SectionBudget("Limitations and Future Work", 400, 300, 600, "extended"),
        SectionBudget("Conclusion", 500, 350, 700, "core"),
    ]

    prohibited_terms = [
        "curriculum learning", "pedagogical", "teaching", "student-teacher",
        "homework", "lesson",
    ]

    preferred_terms = {
        "curriculum learning": "progressive training / multi-stage training / staged training",
        "student-teacher": "knowledge distillation (model compression) / guided training (training strategy)",
        "self-supervised": "self-supervised / unsupervised pre-training",
        "few-shot": "low-data regime / limited supervision",
    }

    writing_style = {
        "tone": "formal and precise, engineering-oriented, signal-processing perspective",
        "argument_depth": "deep — every design choice must be justified with theoretical or empirical evidence",
        "novelty_emphasis": "explicit — clearly state what methodological novelty is new and why it matters for image processing; not just application",
        "experiment_rigor": "extensive — ablation studies, cross-dataset evaluation, statistical analysis, and computational complexity analysis expected",
        "related_work_depth": "thorough — comprehensive coverage with clear categorization; must include most recent baselines",
        "methodology_depth": "detailed — complete mathematical derivations, algorithm pseudocode when applicable; signal-processing rigor",
        "scope_emphasis": "image processing methodology — not pure application, not general CV (that's TPAMI), not medical imaging (that's TMI)",
        "conference_extension": "if extending a conference paper, methodology + ablation + discussion must be substantially expanded (not just reformatting)",
    }

    quality_pass_threshold = 75.0
    num_reviewers = 3
    needs_seven_anchor_test = True
    needs_closed_book_rewrite = True
