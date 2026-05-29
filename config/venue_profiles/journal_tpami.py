# -*- coding: utf-8 -*-
"""IEEE Transactions on Pattern Analysis and Machine Intelligence (TPAMI) — 顶刊配置

调研回顾 (2026):
- IF 20.8, EIC: Kyoung Mu Lee (Seoul National University)
- IEEE Computer Society 出版
- 格式: ~14页 two-column IEEE Transactions format
- 审稿: 3-6个月首次决定, 全流程8-12个月
- Desk rejection 核心筛选:
  1. CV/pattern analysis 方法论创新 (非纯应用)
  2. 全面的 SOTA baseline 对比 (ImageNet/COCO/ADE20K等标准基准)
  3. 会议版本→期刊版本的实质扩展 (方法论+实验+消融+理论)
- 三大拒稿模式:
  1. 会议论文直接转投, 无期刊级扩展
  2. 纯应用论文无方法论创新
  3. 姐妹期刊选错 (TIP/TMI/TMM)
- 关键: abstract+introduction+cover letter 必须明确说明
  方法论贡献, 会议扩展差异, 为何 TPAMI 而非其他期刊
"""

from config.venue_profiles.base_profile import (
    VenueProfile, SectionBudget, FigureRequirement, AblationConfig,
)


class IEEE_TPAMI_Profile(VenueProfile):
    venue_name = "IEEE Transactions on Pattern Analysis and Machine Intelligence"
    venue_type = "journal"
    venue_tier = "top_journal"

    max_pages = 16
    abstract_words = 300
    abstract_max_words = 350

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
        max_ablations=10,
        expected_datasets=4,
        needs_computational_analysis=True,
        needs_failure_analysis=True,
        needs_cross_dataset=True,
        needs_statistical_analysis=True,
        result_table_format="latex_three_line",
    )

    figure_requirements = [
        FigureRequirement("teaser", True, 1, 1, "page_width", "full"),
        FigureRequirement("architecture", True, 1, 2, "page_width", "full"),
        FigureRequirement("comparison", True, 3, 5, "column_width", "full"),
        FigureRequirement("ablation", True, 2, 4, "column_width", "full"),
        FigureRequirement("qualitative", True, 2, 4, "page_width", "full"),
    ]

    section_budgets = [
        SectionBudget("Introduction", 1000, 700, 1400, "core"),
        SectionBudget("Related Work", 1500, 1000, 2200, "core"),
        SectionBudget("Methodology", 3000, 2200, 4000, "core"),
        SectionBudget("Experiments", 2500, 2000, 3500, "core"),
        SectionBudget("Discussion", 800, 500, 1200, "extended"),
        SectionBudget("Limitations and Future Work", 500, 350, 800, "extended"),
        SectionBudget("Conclusion", 600, 400, 800, "core"),
    ]

    prohibited_terms = [
        "curriculum learning", "pedagogical", "teaching", "student-teacher",
    ]
    preferred_terms = {
        "curriculum learning": "progressive training / multi-stage training",
        "student-teacher": "knowledge distillation / guided training",
    }
    writing_style = {
        "tone": "formal, rigorous, theory-grounded — the highest editorial bar among IEEE CV journals",
        "argument_depth": "deepest — every claim needs theoretical grounding or exhaustive empirical proof",
        "novelty_emphasis": "explicit — must articulate novelty over ALL prior art clearly; abstract/intro/cover letter must answer: what changed, why it matters beyond one benchmark, why journal format",
        "experiment_rigor": "exhaustive — comprehensive ablations (5-10), multiple datasets (4+), statistical tests, failure analysis, computational complexity; must use standardized benchmarks (ImageNet, COCO, ADE20K, etc.)",
        "related_work_depth": "most thorough — encyclopedic coverage with clear taxonomy; must include strongest current baselines, not just convenient comparisons",
        "methodology_depth": "most detailed — full derivations, proofs, pseudocode, convergence analysis when applicable",
        "conference_extension": "MUST show substantive journal extension beyond any conference version: extended methodology, additional experiments, broader ablation, theoretical extensions; cover letter must quantify new contributions",
        "scope_emphasis": "general CV/pattern analysis methodology — not image-processing-only (TIP), not medical (TMI), not multimedia (TMM)",
    }

    quality_pass_threshold = 78.0
    num_reviewers = 3
    needs_seven_anchor_test = True
    needs_closed_book_rewrite = True
