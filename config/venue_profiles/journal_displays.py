# -*- coding: utf-8 -*-
"""Displays — Elsevier 期刊配置

调研回顾 (2026):
- Elsevier 出版, peer-reviewed international journal
- 范围: 显示技术和有效呈现/感知信息
  - 显示技术、材料、组件
  - 显示系统、人机交互显示
  - 显示算法 (图像质量增强、色彩管理、HDR)
  - AR/VR 显示、3D 显示、柔性显示
  - 视觉感知与人因工程
- 格式: Elsevier format, "Your Paper Your Way" 初次投稿灵活
- 页数: 建议 ~20页 (无严格限制), Research Article 通常 6000-10000 词
- 审稿: single-blind, 通常 2位 reviewer
- 影响因子: 中等 (~3-4), Scopus indexed
- 关键特色:
  - 偏向显示技术+视觉感知交叉
  - 接收算法论文 (显示相关图像处理, 色彩, HDR, 画质增强)
  - 与 TIP 区别: Displays 侧重显示相关算法, TIP 范围更广
  - 审稿相对友好, 适合显示/视觉感知/图像质量方向
"""

from config.venue_profiles.base_profile import (
    VenueProfile, SectionBudget, FigureRequirement, AblationConfig,
)


class Displays_Profile(VenueProfile):
    venue_name = "Displays"
    venue_type = "journal"
    venue_tier = "good_journal"

    max_pages = 20
    abstract_words = 200
    abstract_max_words = 300

    citation_style = "numeric"
    figure_style = "column_width"
    latex_class = "elsevier"

    sections = [
        "Introduction", "Related Work", "Methodology",
        "Experiments", "Conclusion",
    ]
    extra_sections = ["Discussion"]

    ablation = AblationConfig(
        min_ablations=2,
        max_ablations=5,
        expected_datasets=2,
        needs_computational_analysis=False,
        needs_failure_analysis=False,
        needs_cross_dataset=False,
        needs_statistical_analysis=False,
        result_table_format="latex_three_line",
    )

    figure_requirements = [
        FigureRequirement("teaser", False, 0, 1, "page_width", "full"),
        FigureRequirement("architecture", True, 1, 1, "page_width", "full"),
        FigureRequirement("comparison", True, 1, 3, "column_width", "full"),
        FigureRequirement("ablation", True, 1, 2, "column_width", "moderate"),
        FigureRequirement("qualitative", True, 1, 3, "page_width", "full"),
    ]

    section_budgets = [
        SectionBudget("Introduction", 700, 500, 1000, "core",
                      ["Motivation", "Contributions"]),
        SectionBudget("Related Work", 800, 500, 1200, "core",
                      ["Display Technology Background", "Related Methods"]),
        SectionBudget("Methodology", 1800, 1200, 2800, "core",
                      ["Overview", "Algorithm Details", "Implementation"]),
        SectionBudget("Experiments", 1500, 1000, 2200, "core",
                      ["Setup", "Main Results", "Ablation", "Visual Comparison"]),
        SectionBudget("Discussion", 500, 300, 800, "extended",
                      ["Key Findings", "Practical Implications"]),
        SectionBudget("Conclusion", 400, 250, 600, "core"),
    ]

    prohibited_terms = []
    preferred_terms = {}
    writing_style = {
        "tone": "formal and practical, engineering-oriented with display-technology context",
        "argument_depth": "moderate — focus on practical impact and display-related innovation",
        "novelty_emphasis": "clear — state what display-related problem is solved and how",
        "experiment_rigor": "solid — ablations + visual comparisons; subjective evaluation valued for display research",
        "related_work_depth": "moderate — cover display technology and relevant algorithms",
        "methodology_depth": "moderate — algorithm details + implementation; practical applicability emphasized",
        "visual_quality": "critical — display research values visual quality comparisons; include subjective evaluation when applicable",
        "practical_impact": "important — emphasize practical display applications and real-world relevance",
        "initial_submission_flexibility": "Elsevier 'Your Paper Your Way' — initial format flexible",
    }

    quality_pass_threshold = 68.0
    num_reviewers = 2
    needs_seven_anchor_test = False
    needs_closed_book_rewrite = False
