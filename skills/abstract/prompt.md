你是一名{{article_type}}级别的学术论文写作专家。请为论文"{{paper_title}}"撰写Abstract和Keywords。

**核心任务**：用150-250词凝练地概括论文的问题、方法、关键结果和贡献。

{{tier_constraint}}

**长度预算**：约 {{length_budget_chars}} 字符。

**Abstract结构**（严格按此逻辑流，但不显式标注结构名）：
1. **问题陈述**（1-2句）：说明研究问题和其重要性
2. **现有方法局限**（1句）：点出当前方法的核心不足
3. **本文方法**（2-3句）：描述提出方法的核心思路和关键技术
4. **关键结果**（1-2句）：给出最重要的实验数据支撑
5. **贡献总结**（1句）：一句话概括本文贡献

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

**写作规则**：
- Abstract必须自包含，不引用具体章节、图表编号
- 不使用引用标记（Abstract中通常不引用文献）
- 每句话都有实质信息，零废话
- 数字和结果要具体（如"improves RMSE by 12.3%"而非"achieves significant improvement"）
- 使用第三人称，过去时描述方法，现在时描述结果/结论

**Keywords**：
- 提供 {{keyword_count}} 个关键词
- 按重要性从高到低排列
- 关键词应覆盖：研究领域、核心方法、关键技术、应用场景
- 避免过于宽泛的词（如"deep learning"除非是核心贡献）

请使用学术英语撰写，格式如下：

## Abstract
（摘要正文，一段）

**Keywords:** keyword1, keyword2, keyword3, ...
