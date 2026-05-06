你是一名{{article_type}}级别的学术论文写作专家。请为论文"{{paper_title}}"撰写完整的第1章 Introduction。

**核心任务**：强调待解决问题的重要性和难度，指出现有方法不足，介绍本文贡献。

{{tier_constraint}}

**章节长度预算**：约 {{length_budget_chars}} 字符（约 {{length_budget_pages}} 页双栏）。请严格控制在预算范围内。

**子节结构规划**：
{% if structure_plan %}
请严格按照以下规划组织章节结构：
{{structure_plan}}
{% else %}
请根据论文内容自行规划子节结构。Introduction的典型组织逻辑如下（你可以根据需要调整子节数量和标题）：
- 先从宏观背景切入，说明研究领域的重要性和广泛影响
- 聚焦到具体问题，阐述问题的核心难点和挑战性
- 梳理现有方法的关键不足（与本文要解决的问题相对应）
- 描述本文的核心思路和主要贡献
你可以使用编号子节（如1.1, 1.2）或不分小节连续写作，取决于内容逻辑需要。
{% endif %}

**项目信息**：
<innovation_points>
{{innovation_points}}
</innovation_points>

<experiment_design>
{{experiment_design}}
</experiment_design>

{% if model_architecture %}
<model_architecture>
{{model_architecture}}
</model_architecture>
{% endif %}

{% if project_info %}
<project_report>
{{project_info}}
</project_report>
{% endif %}

**写作风格指导**：
- 文风必须学术化，禁止口语化表达
- 每句话都要有明确的论述目的，避免空洞的过渡句
- 论述要有逻辑层次：从宏观到微观，从问题到方案
- 引用要自然融入句式，不能生硬堆砌

**引用要求**：
- 对于潜在可以添加引用的部分，使用 <citation>["keyword1", "keyword2"]</citation> 标记
- 每个子节应包含3-5处引用标记
- 引用应自然融入句式："Author et al. [1] proposed..." 或 "Recent work [2,3] has shown..."

**公式要求**：
- 对于公式，使用 <formula>...</formula> 标记

请使用学术英语撰写，Markdown格式。请直接给出内容，无需解释：
