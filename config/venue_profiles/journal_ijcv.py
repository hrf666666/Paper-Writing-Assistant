# -*- coding: utf-8 -*-
"""International Journal of Computer Vision (IJCV) — 顶刊配置

调研回顾 (2026):
- IF 11.6, CiteScore 24.0, Springer 出版
- 接受率: ~15-20%, Desk rejection: ~30-40%
- 首次决定: 4-6个月, 全流程: 6-12个月
- 格式: 20-30页, Springer format
- 文章类型: Regular Paper, Short Paper, Survey
- 关键标准:
  1. 理论+实验双重贡献 (不只工程改进)
  2. 会议扩展版需增加至少30%新内容
  3. 全面的 SOTA baseline 对比
  4. 数学/算法新颖性
  5. 可复现性材料
- 三大 desk rejection 原因:
  1. 会议扩展不够 (35% of desk rejections)
  2. baseline 对比不完整 (25%)
  3. 理论贡献薄弱 (20%)
- 与 TPAMI 区别: IJCV 偏 computer vision 理论, TPAMI 范围更广 (pattern analysis)
- Cover letter 要求: 1页, 一句话电梯演讲, 列出相关 IJCV 近期文章
"""

from config.venue_profiles.base_profile import (
    VenueProfile, SectionBudget, FigureRequirement, AblationConfig,
)


class IJCV_Profile(VenueProfile):
    venue_name = "International Journal of Computer Vision"
    venue_type = "journal"
    venue_tier = "top_journal"

    max_pages = 25
    abstract_words = 200
    abstract_max_words = 250

    citation_style = "numeric"
    figure_style = "column_width"
    latex_class = "springer"  # Springer format

    sections = [
        "Introduction", "Related Work", "Methodology",
        "Experiments", "Conclusion",
    ]
    extra_sections = ["Discussion", "Limitations and Future Work", "Appendix"]

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
        FigureRequirement("ablation", True, 2, 4, "column_width", "full"),
        FigureRequirement("qualitative", True, 1, 3, "page_width", "full"),
    ]

    section_budgets = [
        SectionBudget("Introduction", 1200, 800, 1800, "core",
                      ["Motivation", "Contributions", "Paper Organization"]),
        SectionBudget("Related Work", 1500, 1000, 2500, "core",
                      ["Category A", "Category B", "Category C", "Summary and Gap"]),
        SectionBudget("Methodology", 3500, 2500, 5000, "core",
                      ["Overview", "Theoretical Foundation", "Module Details",
                       "Loss Function", "Training Strategy", "Convergence Analysis"]),
        SectionBudget("Experiments", 2500, 1800, 3500, "core",
                      ["Setup", "Main Results", "Ablation Studies",
                       "Cross-dataset Evaluation", "Computational Analysis",
                       "Failure Analysis"]),
        SectionBudget("Discussion", 800, 500, 1200, "extended",
                      ["Key Findings", "Broader Impact", "Insights"]),
        SectionBudget("Limitations and Future Work", 500, 350, 800, "extended"),
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
        "tone": "formal, scholarly, theory-and-evidence grounded",
        "argument_depth": "deepest — every claim needs mathematical grounding or exhaustive empirical proof",
        "novelty_emphasis": "explicit — must articulate mathematical/algorithmic novelty clearly; abstract must state CV method contribution",
        "experiment_rigor": "exhaustive — comprehensive ablations (5-8), multiple datasets (3+), cross-dataset, statistical significance, computational analysis, failure analysis",
        "related_work_depth": "most thorough — encyclopedic coverage with clear taxonomy; must cite recent IJCV articles in the area",
        "methodology_depth": "most detailed — full mathematical derivations, proofs, convergence analysis, algorithm pseudocode",
        "conference_extension": "CRITICAL — must add at least 30% new content beyond any conference version; new theoretical analysis, new experiments, new ablations; cover letter must quantify this explicitly",
        "theoretical_contribution": "required — IJCV expects mathematical or algorithmic novelty, not just engineering improvements",
        "reproducibility": "expected — code, model weights, datasets documentation; 'available upon request' is increasingly flagged",
    }

    quality_pass_threshold = 78.0
    num_reviewers = 3
    needs_seven_anchor_test = True
    needs_closed_book_rewrite = True
