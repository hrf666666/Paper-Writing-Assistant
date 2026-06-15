# -*- coding: utf-8 -*-
"""
项目输入配置
用户只需修改此文件即可配置输入参数

v7.0: 新增 VENUE_TYPE / TARGET_VENUE 精细化配置，
      同时保持 ARTICLE_TYPE 向后兼容。
      venue_profiles 系统会根据 TARGET_VENUE 自动提供
      章节篇幅预算、消融实验数量、图表要求等场景化配置。
"""

import os
from typing import List

# ==================== 必需输入 ====================

# 文章类型: "IEEE Trans" | "ACM Top Conf" | "CCF A" | "CCF B" | 自定义
# 兼容旧配置，同时作为 venue_profiles 的查找键
ARTICLE_TYPE = "IEEE Trans"

# v7.0: 目标 venue 精细化配置（可选，覆盖 ARTICLE_TYPE 的默认映射）
# 设为 None 则按 ARTICLE_TYPE 自动推断
# 支持值: "IEEE TIP" | "IEEE TCSVT" | "IEEE TPAMI" | "CVPR" | "NeurIPS" | None
TARGET_VENUE = "IEEE TCSVT"

# v7.0: venue 类型（可选，覆盖自动推断）
# "journal" | "conference" | None (自动)
VENUE_TYPE = None

# 论文标题
PAPER_TITLE = "Unified Dual-Mask Physical Model for Non-Lambertian Light Field Depth Estimation"

# 作者信息（IEEE 标准格式）
PAPER_AUTHORS = "Ruifeng Huang and Zhenglong Cui"
PAPER_CORRESPONDING_AUTHOR = "Zhenglong Cui"
PAPER_AFFILIATION = "School of Computer Science and Engineering, Beihang University, Beijing, China"
PAPER_EMAIL = "huangruifeng@buaa.edu.cn, czl@buaa.edu.cn"

# 项目实验工程代码路径（包含模型、训练脚本、数据集等）
PROJECT_CODE_PATH = "/home/bigboss/code/depth_estimation_unify_theory"

# v7.0: auto_research_agent 路径（用于消融实验自动化）
# 优先从环境变量读取，未设置则使用默认值
AUTO_RESEARCH_AGENT_PATH = os.getenv("AUTO_RESEARCH_AGENT_PATH", "/home/bigboss/code/auto_research_agent")
AUTO_RESEARCH_AGENT_PYTHON = os.getenv("AUTO_RESEARCH_AGENT_PYTHON", "/home/bigboss/miniconda3/envs/py311/bin/python")

# ==================== 可选输入 ====================

# 参考文章PDF路径（用于学习写作风格和内容组织）
REF_PDF_PATH = "./ref_pdf"

# 输出目录
OUTPUT_DIR = "./output"

# 工作区目录（消融实验代码/图表等中间产出）
WORKSPACE_DIR = "./workspace"

# 是否生成LaTeX代码（True则输出.tex，False则输出.docx）
OUTPUT_LATEX = True

# LaTeX模板选择（当OUTPUT_LATEX=True时生效）
# "ieee_trans" | "acm_conf" | "springer" | 自定义模板路径
LATEX_TEMPLATE = "ieee_trans"

# ==================== 运行时配置 ====================

# 内容审查轮次（独立运行 content_reviewer 时使用）
MAX_REVIEW_ROUNDS = 1

# 参考文献审查（验证可检索性和出处真实性）
CHECK_REFERENCES = True

# 消融实验是否自动运行（需要PROJECT_CODE_PATH下有可运行代码）
RUN_ABLATION = False

# v5.0: 反幻觉审计（参考文献反向检索 + 内容真实性校验 + 步骤完成度检查）
ENABLE_AUDIT = True

# v7.0: 七锚测试（检测论文弧线连贯性）
ENABLE_SEVEN_ANCHOR_TEST = True

# v7.0: 多代理独立审阅
ENABLE_MULTI_REVIEWER = True

# v7.0: 闭卷重写法（提取事实→隐藏原文→蓝图重写）
ENABLE_CLOSED_BOOK_REWRITE = True

# v7.0: 动机驱动写作（强制确认动机后才写作）
ENABLE_MOTIVATION_ENGINE = True

# v7.0: 写作理由矩阵（事前规划型）
ENABLE_RATIONALE_MATRIX = True

# v7.0: 范例学习（从 ref_pdf 深度学习写作决策）
ENABLE_EXEMPLAR_LEARNING = True

# 各章节是否独立生成（True则每章可单独运行，False则必须按顺序）
INDEPENDENT_CHAPTERS = True

# API调用间隔（秒），避免触发频率限制
API_CALL_INTERVAL = 3.0

# ==================== 模型配置（国内优先） ====================
# 模型别名对应 api_config.MODEL_ALIASES 中的条目
# 按优先级排序：国内API优先，国际API作为备选

# 生成模型优先级（GLM 5.2 thinking 优先，跨 provider 降级）
GENERATION_MODELS = [
    "glm_5_2",           # 智谱 GLM-5.2（Coding Plan key, zai SDK, thinking）
    "glm_5_1",           # 智谱 GLM-5.1（zai SDK, thinking）
    "qwen3_7_max",       # 阿里百炼 Qwen3.7-Max（跨 provider 降级）
    "tp_qwen3_7_max",    # 阿里 Token Plan Qwen3.7-Max
    "glm_4_7",           # 智谱 GLM-4.7（zai SDK, thinking）
    "tp_deepseek_v4_pro",# 阿里 Token Plan DeepSeek-V4-Pro
    "tp_qwen3_6_plus",   # 阿里 Token Plan Qwen3.6-Plus
    "glm_5",             # 智谱 GLM-5（zai SDK）
    "tp_deepseek_v4_flash",# 阿里 Token Plan DeepSeek-V4-Flash
    "tp_qwen3_6_flash",  # 阿里 Token Plan Qwen3.6-Flash
    "qwen3_6_plus",      # 阿里百炼 Qwen3.6-Plus（备选）
    "claude_opus_4_7",   # Claude Opus 4.7（需代理）
    "claude_opus_4_6",   # Claude Opus 4.6（需代理）
    "gpt_5_5",           # GPT-5.5（需代理）
    "gpt_5_4",           # GPT-5.4（需代理）
    "gpt_5_3",           # GPT-5.3（需代理）
]

# 推理/决策模型（GLM thinking 优先，跨 provider 降级）
REASONING_MODELS = [
    "glm_5_2",           # 智谱 GLM-5.2（zai SDK, thinking）
    "glm_5_1",           # 智谱 GLM-5.1（zai SDK, thinking）
    "qwen3_7_max",       # 阿里百炼 Qwen3.7-Max（跨 provider 降级）
    "tp_qwen3_7_max",    # Token Plan Qwen3.7-Max
    "glm_4_7",           # 智谱 GLM-4.7（zai SDK, thinking）
    "tp_deepseek_v4_pro",# DeepSeek-V4-Pro（推理强）
    "gpt_5_5",           # GPT-5.5（需代理）
]

# 轻量模型（用于分类/判断等小任务）
LIGHT_MODELS = [
    "tp_qwen3_6_flash",  # Token Plan Qwen3.6-Flash（最快）
    "tp_deepseek_v4_flash",# Token Plan DeepSeek-V4-Flash
    "glm_5",             # 智谱 GLM-5
]

# ==================== 执行-评价模型分离策略 ====================
# 核心原则：评价模型必须与执行模型来自不同 provider（避免"自我审查"盲区）
#
# 策略映射（基于 GENERATION_MODELS 中第一个可用模型）：
#   glm_5.2 执行     → qwen3_7_max 评价（跨 provider）
#   qwen3.7-max 执行 → glm_5_2 评价（跨 provider）
#   仅 GLM 可用     → glm_5.2 执行, glm_5_1 评价（同 provider 降级）
#   仅 Qwen 可用    → qwen3.7-max 执行, qwen3.6-plus 评价（同 provider 降级）
#   仅 Token Plan   → tp_qwen3_7_max 执行, tp_deepseek_v4_pro 评价（不同模型）

# 评价模型优先级（运行时根据执行模型动态选择，见 resolve_eval_models()）
EVALUATION_MODELS = []  # 由 resolve_eval_models() 动态填充


def _detect_execution_provider() -> str:
    """检测当前执行模型所在的 provider"""
    try:
        from config.api_config import MODEL_ALIASES
        for model_name in GENERATION_MODELS:
            if model_name in MODEL_ALIASES:
                return MODEL_ALIASES[model_name]["provider"]
    except Exception:
        pass
    return "unknown"


def resolve_eval_models() -> List[str]:
    """
    根据执行模型动态解析评价模型列表。

    策略：找到执行模型 → 选择不同 provider 的评价模型 → 同 provider 降级兜底
    """
    from config.api_config import MODEL_ALIASES

    # 找到当前执行模型（第一个有 API key 的）
    exec_model = None
    exec_provider = None
    for m in GENERATION_MODELS:
        if m in MODEL_ALIASES:
            exec_model = m
            exec_provider = MODEL_ALIASES[m]["provider"]
            break

    if not exec_model:
        # 无法检测，用 GENERATION_MODELS 做兜底
        return GENERATION_MODELS[1:] if len(GENERATION_MODELS) > 1 else GENERATION_MODELS

    # 构建评价候选列表：优先选择不同 provider 的模型
    cross_provider = []  # 跨 provider
    same_provider = []   # 同 provider

    for m in GENERATION_MODELS:
        if m == exec_model:
            continue
        if m not in MODEL_ALIASES:
            continue
        m_provider = MODEL_ALIASES[m]["provider"]
        if m_provider != exec_provider:
            cross_provider.append(m)
        else:
            same_provider.append(m)

    # 组合：跨 provider 优先 + 同 provider 兜底
    eval_list = cross_provider + same_provider

    if not eval_list:
        # 极端情况：只有一个模型可用，返回自身（不做评价分离）
        return GENERATION_MODELS

    return eval_list


def get_eval_models() -> List[str]:
    """获取评价模型列表（带缓存）"""
    global EVALUATION_MODELS
    if not EVALUATION_MODELS:
        EVALUATION_MODELS = resolve_eval_models()
    return EVALUATION_MODELS


def _resolve_article_type():
    """解析最终生效的 article_type（TARGET_VENUE 优先，否则用 ARTICLE_TYPE）"""
    if TARGET_VENUE is not None:
        return TARGET_VENUE
    return ARTICLE_TYPE


def get_article_type_info():
    """
    根据文章类型返回格式要求（向后兼容）

    v7.0: 优先使用 venue_profiles 系统，降级到旧字典。
    """
    try:
        from config.venue_profiles import get_profile
        from agent.venue_adapter import VenueAdapter
        adapter = VenueAdapter(get_profile(_resolve_article_type()))
        return adapter.to_legacy_dict()
    except Exception:
        pass

    # 降级：旧版硬编码字典
    article_profiles = {
        "IEEE Trans": {
            "name": "IEEE Transactions",
            "citation_style": "numeric",
            "figure_style": "column_width",
            "max_pages": 14,
            "abstract_words": 250,
            "sections": ["Introduction", "Related Work", "Methodology", "Experiments", "Conclusion"],
            "latex_class": "IEEEtran",
            "tier": "top_journal",
            "prohibited_terms": [
                "curriculum learning", "pedagogical", "teaching",
                "student-teacher", "homework", "lesson",
            ],
            "preferred_terms": {
                "curriculum learning": "progressive training / multi-stage training / staged training",
                "student-teacher": "knowledge distillation / guided training",
                "self-supervised": "self-supervised / unsupervised pre-training",
                "few-shot": "low-data regime / limited supervision",
            },
            "writing_style": {
                "tone": "formal and precise, engineering-oriented",
                "argument_depth": "deep — every design choice must be justified with theoretical or empirical evidence",
                "novelty_emphasis": "explicit — clearly state what is new and why it matters compared to prior art",
                "experiment_rigor": "extensive — ablation studies, cross-dataset evaluation, and statistical analysis expected",
                "related_work_depth": "thorough — comprehensive coverage with clear categorization",
                "methodology_depth": "detailed — complete mathematical derivations, algorithm pseudocode when applicable",
            },
        },
        "ACM Top Conf": {
            "name": "ACM Conference",
            "citation_style": "numeric",
            "figure_style": "column_width",
            "max_pages": 12,
            "abstract_words": 200,
            "sections": ["Introduction", "Related Work", "Methodology", "Experiments", "Conclusion"],
            "latex_class": "acmart",
            "tier": "top_conference",
            "prohibited_terms": ["curriculum learning", "pedagogical"],
            "preferred_terms": {
                "curriculum learning": "progressive training / staged training",
                "student-teacher": "knowledge distillation / guided training",
            },
            "writing_style": {
                "tone": "formal and impactful, emphasize novelty",
                "argument_depth": "moderate — focus on key insights and innovations",
                "novelty_emphasis": "strong — highlight novelty early and often",
                "experiment_rigor": "solid — main comparisons + ablations",
                "related_work_depth": "concise — focused on most relevant work",
                "methodology_depth": "moderate — key formulations + architecture description",
            },
        },
        "CCF A": {
            "name": "CCF A Class",
            "citation_style": "numeric",
            "figure_style": "column_width",
            "max_pages": 14,
            "abstract_words": 250,
            "sections": ["Introduction", "Related Work", "Methodology", "Experiments", "Conclusion"],
            "latex_class": "IEEEtran",
            "tier": "top_venue",
            "prohibited_terms": ["curriculum learning", "pedagogical"],
            "preferred_terms": {
                "curriculum learning": "progressive training / multi-stage training",
                "student-teacher": "knowledge distillation / guided training",
            },
            "writing_style": {
                "tone": "formal and rigorous",
                "argument_depth": "deep — thorough justification required",
                "novelty_emphasis": "explicit — clearly articulate contributions",
                "experiment_rigor": "extensive — comprehensive evaluation",
                "related_work_depth": "thorough — well-categorized survey",
                "methodology_depth": "detailed — complete formulations and derivations",
            },
        },
        "CCF B": {
            "name": "CCF B Class",
            "citation_style": "numeric",
            "figure_style": "column_width",
            "max_pages": 12,
            "abstract_words": 200,
            "sections": ["Introduction", "Related Work", "Methodology", "Experiments", "Conclusion"],
            "latex_class": "IEEEtran",
            "tier": "good_venue",
            "prohibited_terms": ["curriculum learning", "pedagogical"],
            "preferred_terms": {"curriculum learning": "progressive training / staged training"},
            "writing_style": {
                "tone": "formal, clear and practical",
                "argument_depth": "moderate — clear motivation and reasonable evidence",
                "novelty_emphasis": "moderate — highlight improvements over baselines",
                "experiment_rigor": "solid — standard comparisons and ablations",
                "related_work_depth": "adequate — cover key related work",
                "methodology_depth": "moderate — describe approach clearly with key formulations",
            },
        },
    }
    return article_profiles.get(ARTICLE_TYPE, article_profiles["IEEE Trans"])


def get_tier_prompt_block():
    """获取论文等级约束的prompt注入块（用于所有章节生成）"""
    try:
        from agent.venue_adapter import get_active_profile
        profile = get_active_profile()  # 使用 resolve_article_type，TARGET_VENUE 优先
        venue_block = f"目标期刊: {profile.venue_name}\n类型: {profile.venue_type}"
        return f"\n{venue_block}\n\n3. **术语规范**：\n   - 使用本领域标准术语\n   - 训练策略描述：使用 progressive training / staged training\n   - 知识迁移：使用 knowledge distillation / guided training\n"
    except Exception:
        pass

    # 降级逻辑
    info = get_article_type_info()
    tier = info.get("tier", "top_journal")
    prohibited = info.get("prohibited_terms", [])
    preferred = info.get("preferred_terms", {})
    style = info.get("writing_style", {})

    block = f"""
**论文等级约束**（{info['name']} - {tier}）：
1. **禁用术语**：以下术语不得出现在论文中，因为它们属于其他学科领域或不适合本论文等级：
"""
    for term in prohibited:
        replacement = preferred.get(term, "请使用更准确的CS学术术语")
        block += f'   - "{term}" → 应使用: {replacement}\n'

    block += """
2. **写作风格要求**：
"""
    for key, desc in style.items():
        label = {
            "tone": "文风基调",
            "argument_depth": "论证深度",
            "novelty_emphasis": "创新强调",
            "experiment_rigor": "实验严谨度",
            "related_work_depth": "相关工作深度",
            "methodology_depth": "方法描述深度",
        }.get(key, key)
        block += f"   - {label}: {desc}\n"

    block += """
3. **术语规范**：
   - 使用本领域（计算机视觉/计算摄影/深度估计）的标准术语
   - 训练策略描述：使用"progressive training"/"staged training"/"multi-stage training"，而非教育领域术语
   - 知识迁移：使用"knowledge distillation"（模型压缩）/ "guided training"（训练策略）
   - 如不确定某术语是否恰当，优先使用更中性的技术描述
"""
    return block
