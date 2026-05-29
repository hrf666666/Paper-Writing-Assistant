# -*- coding: utf-8 -*-
"""
IEEE Transactions 期刊风格配置文件

基于 journal-adapt-writing-skill 的 Style Profile 概念
将 IEEE Trans 的写作规范结构化为可加载的配置

此配置文件作为 P2（目标期刊）优先级规则，覆盖 P4（静态基础规则）
"""

# IEEE Transactions 期刊元信息
JOURNAL_META = {
    "name": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
    "abbr": "IEEE TPAMI",
    "discipline": "Computer Vision / Machine Learning",
    "method_types": ["theory", "empirical", "simulation", "mixed"],
    "implied_reader": "academic specialist with strong technical background",
}

# 编辑身份 (Editorial Identity)
EDITORIAL_IDENTITY = {
    "research_question_type": "Novel methods with rigorous theoretical analysis and comprehensive empirical validation",
    "methods_valued": ["deep learning architectures", "optimization algorithms", "theoretical analysis", "benchmark comparisons"],
    "implied_reader": "academic specialist",
}

# Introduction 规范 (来自 journal-adapt Style Profile)
INTRODUCTION_CONVENTIONS = [
    {
        "pattern": "Opens with problem motivation, not field history",
        "corpus_role": "primary",
        "description": "开篇直接陈述问题动机，避免 'Deep learning has revolutionized...' 等陈词滥调",
    },
    {
        "pattern": "Limitations of existing approaches stated before proposed method",
        "corpus_role": "primary",
        "description": "在介绍本文方法前，先明确现有方法的局限性",
    },
    {
        "pattern": "Contributions as bulleted list (2-3 items)",
        "corpus_role": "primary",
        "description": "贡献以列表形式呈现，2-3 项，每项是具体可验证的声明",
    },
    {
        "pattern": "Contributions stated as facts, not intentions",
        "corpus_role": "primary",
        "description": "'We propose X that achieves Y' 而非 'We aim to address Z'",
    },
    {
        "pattern": "Paper structure roadmap at end of intro",
        "corpus_role": "primary",
        "description": "Introduction 末尾包含论文组织结构",
    },
]

# 贡献表达规范
CONTRIBUTION_EXPRESSION = {
    "voice": "we propose / we present / our method achieves",
    "claim_strength": "strong assertion with empirical backing",
    "number_of_contributions": "2-3 specific, verifiable claims",
    "format": "bulleted list or numbered paragraphs",
    "anti_patterns": [
        "This paper explores...",
        "In this study, we aim to...",
        "We leave X for future work (without specific direction)",
    ],
}

# 文献综述规范
LITERATURE_REVIEW_NORMS = {
    "structure": "standalone section after introduction",
    "organization": "by approach or technique, not chronologically",
    "critical_engagement": "compare-contrast with clear differentiation",
    "citation_density": "3-5 most relevant papers per claim, not 10+",
    "required_elements": [
        "what they do",
        "what they cannot do",
        "how ours differs",
    ],
}

# 方法/模型规范
METHOD_NORMS = {
    "entry_point": "intuition before formalism",
    "notation_density": "moderate to heavy, with all notation defined before first use",
    "exposition_style": "proposition-then-proof / architecture-walkthrough",
    "assumption_justification": "explicit for non-obvious design choices",
    "required_elements": [
        "overall architecture figure",
        "notation consistency throughout",
        "algorithm pseudocode with line numbers (if applicable)",
    ],
}

# 结果与讨论规范
RESULTS_DISCUSSION_NORMS = {
    "primary_vehicle": "tables with all baselines, bold best result",
    "narrative_style": "result → mechanism → implication",
    "mechanism_emphasis": "central",
    "robustness_signaling": "ablation studies after main results",
    "required_elements": [
        "experimental setup (datasets, metrics, baselines, implementation details)",
        "main results table with statistical significance if applicable",
        "ablation studies (one component at a time)",
        "failure case analysis",
    ],
}

# 语言风格画像 (Language Style Profile)
LANGUAGE_STYLE_PROFILE = {
    "voice": "active-dominant (we propose, we show, our model achieves)",
    "sentence_length": "varied, ideal 20-30 words, max 40 words",
    "hedging_level": "medium (retain strong hedging when genuine uncertainty exists)",
    "mathematical_density": "heavy (equations introduced in words before displaying)",
    "transition_style": "structural headers and explicit connectives",
}

# 冲突解决表 (Conflict Table: Corpus Signals vs Static Base Rules)
CONFLICT_RESOLUTION = {
    "voice": {
        "static_base": "active preferred, passive acceptable where convention demands",
        "target_journal": "active-dominant in method/results, passive in experimental setup",
        "resolution": "target_journal wins",
    },
    "contribution_format": {
        "static_base": "2-4 specific claims",
        "target_journal": "2-3 bulleted items, stated as facts",
        "resolution": "target_journal wins (more specific)",
    },
    "hedging": {
        "static_base": "retain strong hedging for genuine uncertainty",
        "target_journal": "medium hedging, avoid overclaiming",
        "resolution": "consistent, both support medium hedging",
    },
    "literature_placement": {
        "static_base": "standalone section or integrated into intro",
        "target_journal": "standalone section after introduction",
        "resolution": "target_journal wins",
    },
}

# Red Flags (期刊中不存在的写作模式)
RED_FLAGS = [
    "Opening with 'Deep learning has revolutionized...' or similar clichés",
    "Listing 5+ contributions (weakens all of them)",
    "Promising results not delivered by end of paper",
    "Dismissing prior work without showing full understanding",
    "Omitting hyperparameter settings (blocks reproducibility)",
    "Cherry-picking qualitative examples without quantitative support",
    "Using 'novel', 'innovative', 'state-of-the-art' as self-descriptions before results",
    "Conclusion introducing new methods or results",
]

# 章节特定要求 (Section-Specific Requirements)
SECTION_REQUIREMENTS = {
    "Abstract": {
        "structure": "problem → limitation of prior work → proposed method → key results (with numbers) → significance",
        "length": "150-250 words",
        "must_include": [
            "at least one concrete metric result",
            "method/model name if applicable",
        ],
        "tense": "past for experiments, present for method claims",
        "anti_patterns": [
            '"novel", "innovative", "state-of-the-art" as self-descriptions',
            '"Deep learning has revolutionized..." opening',
        ],
    },
    "Introduction": {
        "structure": "problem motivation → limitations of existing approaches → your approach (high-level) → contributions (bulleted) → paper structure",
        "contributions": {
            "max_items": 3,
            "format": "concrete, verifiable claims as facts, not intentions",
        },
        "anti_patterns": [
            '"Deep learning has revolutionized..." opening',
            "5+ contributions",
            "promising undelivered results",
        ],
    },
    "Related Work": {
        "organization": "by approach or technique, not chronologically",
        "per_group": "what they do + what they cannot do + how ours differs",
        "citation_density": "3-5 most relevant papers per claim",
        "anti_patterns": [
            "dismissing prior work",
            "chronological organization",
        ],
    },
    "Method": {
        "entry": "intuition before formalism",
        "required": [
            "overall architecture figure",
            "all notation defined before first use",
            "notation consistency throughout",
        ],
        "anti_patterns": [
            "formalism before intuition",
            "undefined notation",
            "inconsistent notation",
        ],
    },
    "Experiments": {
        "structure": "setup → main results → ablation studies → analysis",
        "setup_must_include": [
            "datasets",
            "evaluation metrics",
            "baselines",
            "implementation details (optimizer, LR, hardware, seeds)",
        ],
        "main_results": "table with all baselines, bold best result, statistical significance if applicable",
        "ablation": "one component at a time, each tests one design decision",
        "anti_patterns": [
            "only accuracy reported",
            "cherry-picked examples without quantitative support",
            "omitted hyperparameter settings",
        ],
    },
    "Conclusion": {
        "length": "2-3 sentences for contribution summary",
        "must_include": [
            "honest limitations",
            "one specific future direction",
        ],
        "anti_patterns": [
            "generic 'more research needed' calls",
            "new methods or results introduced",
        ],
    },
}


def get_ieee_trans_style_profile() -> dict:
    """
    获取 IEEE Trans 期刊风格配置
    
    Returns:
        dict: 完整的风格配置字典
    """
    return {
        "journal_meta": JOURNAL_META,
        "editorial_identity": EDITORIAL_IDENTITY,
        "introduction_conventions": INTRODUCTION_CONVENTIONS,
        "contribution_expression": CONTRIBUTION_EXPRESSION,
        "literature_review_norms": LITERATURE_REVIEW_NORMS,
        "method_norms": METHOD_NORMS,
        "results_discussion_norms": RESULTS_DISCUSSION_NORMS,
        "language_style_profile": LANGUAGE_STYLE_PROFILE,
        "conflict_resolution": CONFLICT_RESOLUTION,
        "red_flags": RED_FLAGS,
        "section_requirements": SECTION_REQUIREMENTS,
    }


def get_section_requirements(section_name: str) -> dict:
    """
    获取特定章节的要求
    
    Args:
        section_name: 章节名称 (Abstract, Introduction, Related Work, Method, Experiments, Conclusion)
    
    Returns:
        dict: 章节要求字典
    """
    return SECTION_REQUIREMENTS.get(section_name, {})


def get_red_flags() -> list:
    """获取 Red Flags 列表"""
    return RED_FLAGS


def get_language_style() -> dict:
    """获取语言风格画像"""
    return LANGUAGE_STYLE_PROFILE
