# -*- coding: utf-8 -*-
"""ECCV — European Conference on Computer Vision 顶会配置

调研回顾 (ECCV 2026):
- 页数: 14页 (含图表), LNCS/Springer 格式, 参考文献不限页数
- 格式: ECCV style (基于 Springer LNCS), double-blind review
- 周期: 双年举办 (偶数年: ECCV, 奇数年: ICCV)
- ECCV 2026 新增 Contribution Types:
  1. Algorithms/General
  2. Theory/Foundational
  3. Applied/Systems
  4. Datasets/Benchmarks
- 审稿: 3位 reviewer + discussion phase + author rebuttal
- 关键特色:
  - 14页比 CVPR/ICCV 的8页充裕得多, 可以更充分展开
  - reviewer 看重: novelty + potential impact, 不只看 SOTA accuracy
  - 鼓励新颖大胆的概念, 即使未在多个数据集测试
  - 鼓励讨论 limitations, 正面评价 honest discussion
  - 不允许 LLM 生成/辅助审稿
- 严格 deadline: reviewer 不按时提交 = 其本人论文 desk reject
"""

from config.venue_profiles.base_profile import (
    VenueProfile, SectionBudget, FigureRequirement, AblationConfig,
)


class ECCV_Profile(VenueProfile):
    venue_name = "European Conference on Computer Vision"
    venue_type = "conference"
    venue_tier = "top_conference"

    max_pages = 14
    abstract_words = 250
    abstract_max_words = 300

    citation_style = "numeric"
    figure_style = "column_width"
    latex_class = "eccv"  # Springer LNCS style

    sections = [
        "Introduction", "Related Work", "Methodology",
        "Experiments", "Conclusion",
    ]
    extra_sections = ["Limitations Discussion"]

    ablation = AblationConfig(
        min_ablations=3,
        max_ablations=5,
        expected_datasets=2,
        needs_computational_analysis=False,
        needs_failure_analysis=False,
        needs_cross_dataset=True,
        needs_statistical_analysis=False,
        result_table_format="latex_three_line",
    )

    figure_requirements = [
        FigureRequirement("teaser", True, 1, 1, "page_width", "full"),
        FigureRequirement("architecture", True, 1, 1, "page_width", "full"),
        FigureRequirement("comparison", True, 1, 3, "column_width", "moderate"),
        FigureRequirement("ablation", True, 1, 2, "column_width", "moderate"),
        FigureRequirement("qualitative", True, 0, 2, "page_width", "moderate"),
    ]

    section_budgets = [
        SectionBudget("Introduction", 700, 500, 1000, "core",
                      ["Motivation", "Contributions"]),
        SectionBudget("Related Work", 600, 400, 900, "core",
                      ["Category 1", "Category 2", "Summary"]),
        SectionBudget("Methodology", 2200, 1600, 3000, "core",
                      ["Overview", "Module Details", "Training"]),
        SectionBudget("Experiments", 1500, 1000, 2200, "core",
                      ["Setup", "Main Results", "Ablation Studies", "Cross-dataset"]),
        SectionBudget("Limitations Discussion", 400, 200, 600, "extended",
                      ["Honest Limitations", "Future Directions"]),
        SectionBudget("Conclusion", 350, 200, 500, "core"),
    ]

    prohibited_terms = [
        "curriculum learning", "pedagogical",
    ]
    preferred_terms = {
        "curriculum learning": "progressive training / staged training",
        "student-teacher": "knowledge distillation / guided training",
    }
    writing_style = {
        "tone": "formal and thoughtful, emphasize insight, novelty and potential impact over raw accuracy",
        "argument_depth": "moderate-to-deep — ECCV values novel and brave concepts even without exhaustive testing",
        "novelty_emphasis": "strong — highlight what is fundamentally new; not beating SOTA on one benchmark is NOT grounds for rejection by itself",
        "experiment_rigor": "solid — main comparisons + ablations; cross-dataset evaluation valued; supplementary for extended results",
        "related_work_depth": "moderate — more thorough than CVPR/ICCV due to 14-page format, but still focused",
        "methodology_depth": "moderate-to-detailed — 14 pages allow more space for derivations and architecture details",
        "limitations_emphasis": "positive — ECCV explicitly encourages honest discussion of limitations; reviewers weight this POSITIVELY, not as penalty",
        "reproducibility": "encouraged — code submission as supplementary is highly valued",
        "contribution_type": "ECCV 2026+ uses Contribution Types (Algorithms/Theory/Applied/Datasets) — align writing with declared type",
    }

    quality_pass_threshold = 73.0
    num_reviewers = 3
    needs_seven_anchor_test = True
    needs_closed_book_rewrite = False
