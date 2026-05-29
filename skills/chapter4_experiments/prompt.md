你是一名{{article_type}}级别的学术论文写作专家。请为论文"{{paper_title}}"撰写完整的第4章 Experiments。

**核心任务**：通过多维度实验验证方法有效性，包含定量分析和定性分析。

{{tier_constraint}}

**章节长度预算**：约 {{length_budget_chars}} 字符。

**子节结构规划**：
{% if structure_plan %}
请严格按照以下规划组织章节结构：
{{structure_plan}}
{% else %}
请根据实验设计自行规划子节结构。实验章节的典型组织逻辑：
- 实验设置（数据集、评价指标、实现细节）
- 与现有方法的定量比较（主实验）
- 消融实验（验证各组件贡献）
- 定性分析/可视化
- （可选）跨域泛化/鲁棒性分析
你可以根据实验设计数据调整子节数量和顺序。
{% endif %}

**实验设计数据**：
<experiment_design>
{{experiment_design}}
</experiment_design>

**创新点**（确定消融实验重点）：
{{innovation_points}}

{% if model_architecture %}
**模型架构**：
{{model_architecture}}
{% endif %}

**写作规则**：
1. 每个实验子节要有明确的验证目标
2. 实验结果用表格呈现，配合文字分析
3. 表格格式：<table>标题 | 列定义 | 数据行</table>
4. 不只报数字，要分析数字背后的原因
5. 消融实验要逐个移除核心组件，验证每个创新的独立贡献
6. 引用使用 <citation>["keyword1", "keyword2"]</citation> 标记
7. 定性分析要提供具体案例说明方法优势

**详略分布**：
- 主实验和消融实验：详写（各占2-3段 + 表格）
- 实验设置和定性分析：适度（各1-2段）

请使用学术英语撰写，Markdown格式。直接给出内容：
