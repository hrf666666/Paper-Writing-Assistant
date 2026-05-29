# -*- coding: utf-8 -*-
"""AAAI — AAAI Conference on Artificial Intelligence 顶会配置

调研回顾 (AAAI-26, 2026):
- 页数: 7页正文 (不含参考文献+reproducibility checklist), AAAI two-column style
- 格式: AAAI Press camera-ready style, double-blind review
- 投稿量: ~30,000 submissions (AAAI-26, 史无前例)
- 审稿流程: Two-Phase Review
  - Phase 1: 3位 reviewer, 负面评价过多直接 reject
  - Phase 2: 分配额外 reviewer (不看 Phase 1 评价)
  - Discussion + Author Feedback (Oct 7-13)
- AAAI-26 新增: AI-assisted peer review pilot (LLM 辅助初审)
- 范围: AI 全领域, 不限于 CV
  - 机器学习、自然语言处理、知识表示、规划、搜索、多智能体...
  - CV 论文投 AAAI 需强调 AI/ML 角度, 非纯 CV
- 关键: 紧凑格式 (7页), 需要在有限空间内展示清晰贡献
  - 与 CVPR/ICCV 区别: AAAI 受众更广, 需要为非 CV 专家解释动机
  - 偏好: 理论+算法创新, 不要求 exhaustive experiment
"""

from config.venue_profiles.base_profile import (
    VenueProfile, SectionBudget, FigureRequirement, AblationConfig,
)


class AAAI_Profile(VenueProfile):
    venue_name = "AAAI Conference on Artificial Intelligence"
    venue_type = "conference"
    venue_tier = "top_conference"

    max_pages = 7
    abstract_words = 200
    abstract_max_words = 250

    citation_style = "numeric"
    figure_style = "column_width"
    latex_class = "aaai"

    sections = [
        "Introduction", "Related Work", "Methodology",
        "Experiments", "Conclusion",
    ]
    extra_sections = []

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
        FigureRequirement("teaser", False, 0, 1, "page_width", "moderate"),
        FigureRequirement("architecture", True, 1, 1, "page_width", "moderate"),
        FigureRequirement("comparison", True, 1, 2, "column_width", "moderate"),
        FigureRequirement("ablation", True, 1, 1, "column_width", "minimal"),
        FigureRequirement("qualitative", False, 0, 1, "column_width", "minimal"),
    ]

    section_budgets = [
        SectionBudget("Introduction", 450, 300, 600, "core",
                      ["Motivation", "Contributions"]),
        SectionBudget("Related Work", 300, 200, 450, "core",
                      ["Most Relevant"]),
        SectionBudget("Methodology", 1200, 900, 1600, "core",
                      ["Overview", "Key Algorithm"]),
        SectionBudget("Experiments", 800, 600, 1100, "core",
                      ["Setup", "Main Results", "Ablation"]),
        SectionBudget("Conclusion", 200, 150, 350, "core"),
    ]

    prohibited_terms = [
        "curriculum learning", "pedagogical",
    ]
    preferred_terms = {
        "curriculum learning": "progressive training / staged training",
        "student-teacher": "knowledge distillation / guided training",
    }
    writing_style = {
        "tone": "formal and accessible, AI-broad-audience-oriented",
        "argument_depth": "moderate — focus on key insights and algorithmic innovation; explain for non-domain experts",
        "novelty_emphasis": "strong — highlight AI/ML contribution, not domain-specific results",
        "experiment_rigor": "solid — main comparisons + compact ablations; theoretical analysis valued",
        "related_work_depth": "concise — focused on AI/ML positioning, not exhaustive CV survey",
        "methodology_depth": "moderate — key formulations + algorithm; audience is AI-general, avoid excessive domain jargon",
        "cross_domain_appeal": "critical — AAAI audience spans all AI subfields; must explain why this matters to AI beyond one application",
        "brevity": "extreme — only 7 pages, every sentence must count; no fluff, no verbose background",
    }

    quality_pass_threshold = 70.0
    num_reviewers = 1
    needs_seven_anchor_test = False
    needs_closed_book_rewrite = False
