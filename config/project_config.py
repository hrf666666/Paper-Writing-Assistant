# -*- coding: utf-8 -*-
"""
项目输入配置
用户只需修改此文件即可配置输入参数
"""

# ==================== 必需输入 ====================

# 文章类型: "IEEE Trans" | "ACM Top Conf" | "CCF A" | "CCF B" | 自定义
ARTICLE_TYPE = "IEEE Trans"

# 论文标题
PAPER_TITLE = "Unified Dual-Mask Physical Model for Non-Lambertian Light Field Depth Estimation"

# 项目实验工程代码路径（包含模型、训练脚本、数据集等）
PROJECT_CODE_PATH = "./workspace/project_code"

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
MAX_REVIEW_ROUNDS = 2

# 参考文献审查（验证可检索性和出处真实性）
CHECK_REFERENCES = True

# 消融实验是否自动运行（需要PROJECT_CODE_PATH下有可运行代码）
RUN_ABLATION = False

# v5.0: 反幻觉审计（参考文献反向检索 + 内容真实性校验 + 步骤完成度检查）
ENABLE_AUDIT = True

# 各章节是否独立生成（True则每章可单独运行，False则必须按顺序）
INDEPENDENT_CHAPTERS = True

# API调用间隔（秒），避免触发频率限制
API_CALL_INTERVAL = 3.0

# ==================== 模型配置（国内优先） ====================
# 模型别名对应 api_config.MODEL_ALIASES 中的条目
# 按优先级排序：国内API优先，国际API作为备选

# 生成模型优先级（国内优先）
GENERATION_MODELS = [
    "glm_5_1",        # 智谱GLM-5.1（主力生成模型）
    "qwen3_6_plus",   # 阿里云百炼 Qwen3.6-Plus
    "glm_4_plus",     # 智谱GLM-4-Plus
    "claude_37",      # Claude 3.7 Sonnet（需代理）
    "o3_mini",        # OpenAI o3-mini（需代理）
]

# 推理/决策模型（国内优先）
REASONING_MODELS = [
    "glm_5_1",        # 智谱GLM-5.1
    "qwq_32b",        # 阿里云百炼 QwQ-32B
    "o1",             # OpenAI o1（需代理）
]

# 轻量模型（用于分类/判断等小任务，国内优先）
LIGHT_MODELS = [
    "glm_4_flash",    # 智谱GLM-4-Flash（最快最便宜）
    "qwen_plus",      # 阿里云百炼 Qwen-Plus
    "qwen_72b",       # 阿里云百炼 Qwen-72B-Instruct
]


def get_article_type_info():
    """根据文章类型返回格式要求"""
    article_profiles = {
        "IEEE Trans": {
            "name": "IEEE Transactions",
            "citation_style": "numeric",      # [1], [2] 数字引用
            "figure_style": "column_width",    # 单栏宽图
            "max_pages": 14,
            "abstract_words": 250,
            "sections": ["Introduction", "Related Work", "Methodology", "Experiments", "Conclusion"],
            "latex_class": "IEEEtran",
            # ---- v4: 论文等级语义约束 ----
            "tier": "top_journal",
            "prohibited_terms": [
                "curriculum learning",  # 教育领域术语，CS论文中用"progressive training"/"staged training"/"multi-stage training"
                "pedagogical",          # 教育领域
                "teaching",             # 教育领域（指教学法时）
                "student-teacher",      # 应用蒸馏时用"knowledge distillation"，描述训练策略时用"guided training"
                "homework",
                "lesson",
            ],
            "preferred_terms": {
                "curriculum learning": "progressive training / multi-stage training / staged training",
                "student-teacher": "knowledge distillation (if referring to model compression) / guided training (if referring to training strategy)",
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
            "prohibited_terms": [
                "curriculum learning",
                "pedagogical",
            ],
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
            "prohibited_terms": [
                "curriculum learning",
                "pedagogical",
            ],
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
            "prohibited_terms": [
                "curriculum learning",
                "pedagogical",
            ],
            "preferred_terms": {
                "curriculum learning": "progressive training / staged training",
            },
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
