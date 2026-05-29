# -*- coding: utf-8 -*-
"""Pattern Recognition (PR) — Elsevier 期刊配置

调研回顾 (2026):
- IF ~7.6 (2025), CiteScore 13.1, JCR Q1
- Elsevier 出版, IAPR (International Association for Pattern Recognition) 关联
- 格式: Elsevier format, single-column double-spaced
- 页数: 20-35页 (含图表), review paper 可到40页
- 审稿: single-blind peer review
- 范围: 模式识别全领域
  - 图像分析、目标检测、人脸识别、模式分析
  - 机器学习、统计模式识别、神经网络
  - 文档分析、语音识别、生物特征识别
- 关键特色:
  - 偏好理论+实验并重, 数学基础扎实
  - 与 TIP 区别: PR 更侧重模式识别理论/方法, TIP 侧重图像处理
  - 与 TPAMI 区别: PR 的范围更偏向传统 PR+ML, TPAMI 更偏向现代 CV/DL
  - Elsevier "Your Paper Your Way": 初次投稿格式灵活, 修订时才需排版
"""

from config.venue_profiles.base_profile import (
    VenueProfile, SectionBudget, FigureRequirement, AblationConfig,
)


class PatternRecognition_Profile(VenueProfile):
    venue_name = "Pattern Recognition"
    venue_type = "journal"
    venue_tier = "top_journal"

    max_pages = 30
    abstract_words = 250
    abstract_max_words = 300

    citation_style = "numeric"
    figure_style = "column_width"
    latex_class = "elsevier"  # Elsevier format

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
        needs_failure_analysis=False,
        needs_cross_dataset=True,
        needs_statistical_analysis=True,
        result_table_format="latex_three_line",
    )

    figure_requirements = [
        FigureRequirement("teaser", False, 0, 1, "page_width", "full"),
        FigureRequirement("architecture", True, 1, 2, "page_width", "full"),
        FigureRequirement("comparison", True, 2, 4, "column_width", "full"),
        FigureRequirement("ablation", True, 1, 3, "column_width", "moderate"),
        FigureRequirement("qualitative", True, 1, 2, "page_width", "full"),
    ]

    section_budgets = [
        SectionBudget("Introduction", 900, 600, 1300, "core",
                      ["Motivation", "Contributions", "Paper Organization"]),
        SectionBudget("Related Work", 1300, 900, 2000, "core",
                      ["Category A", "Category B", "Category C", "Summary and Gap"]),
        SectionBudget("Methodology", 2500, 1800, 3800, "core",
                      ["Problem Formulation", "Proposed Method", "Theoretical Analysis",
                       "Algorithm", "Complexity Analysis"]),
        SectionBudget("Experiments", 2000, 1500, 3000, "core",
                      ["Setup", "Main Results", "Ablation Studies",
                       "Cross-dataset Evaluation", "Statistical Analysis"]),
        SectionBudget("Discussion", 600, 400, 900, "extended",
                      ["Key Findings", "Analysis"]),
        SectionBudget("Limitations and Future Work", 400, 300, 600, "extended"),
        SectionBudget("Conclusion", 500, 350, 700, "core"),
    ]

    prohibited_terms = [
        "curriculum learning", "pedagogical",
    ]
    preferred_terms = {
        "curriculum learning": "progressive training / staged training",
        "student-teacher": "knowledge distillation / guided training",
    }
    writing_style = {
        "tone": "formal, analytical, theory-grounded — pattern recognition research tradition",
        "argument_depth": "deep — solid theoretical foundation with rigorous empirical validation",
        "novelty_emphasis": "explicit — must articulate pattern recognition methodology novelty clearly",
        "experiment_rigor": "extensive — ablations (4-7), multiple datasets (3+), statistical significance tests valued",
        "related_work_depth": "thorough — broad coverage of PR literature with clear categorization",
        "methodology_depth": "detailed — mathematical formulations, algorithm pseudocode, theoretical analysis",
        "statistical_rigor": "valued — PR tradition emphasizes statistical pattern recognition; include significance tests, confidence intervals",
        "scope_emphasis": "pattern recognition theory and methodology — includes but not limited to CV; ML/statistical methods welcome",
        "initial_submission_flexibility": "Elsevier 'Your Paper Your Way' — initial submission format is flexible, only final version needs Elsevier formatting",
    }

    quality_pass_threshold = 73.0
    num_reviewers = 3
    needs_seven_anchor_test = True
    needs_closed_book_rewrite = True
