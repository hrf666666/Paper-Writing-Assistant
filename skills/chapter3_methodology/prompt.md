你是一名{{article_type}}级别的学术论文写作专家。请为论文"{{paper_title}}"撰写完整的第3章 Methodology。

**核心任务**：清晰描述方法设计，核心创新模块详写，基础组件略写。

{{tier_constraint}}

**章节长度预算**：约 {{length_budget_chars}} 字符（约 {{length_budget_pages}} 页）。

**详略分布规则**（严格遵守）：
- **核心创新模块**（与innovation_points直接对应的）：详写，每个2-3段，包含：
  - 设计动机和直觉
  - 完整的数学公式（使用 <formula>...</formula> 标记）
  - 与现有方法的关键区别
  - 伪代码或算法描述（如适用）
  
- **基础/辅助组件**：略写，每个0.5-1段，包含：
  - 简要描述核心思路
  - 关键公式
  - 引用原始论文即可

**方法架构概览**：
{{model_architecture}}

**创新点**（确定详写重点）：
{{innovation_points}}

{% if experiment_design %}
**实验设计**（用于确定消融实验需要的组件描述深度）：
{{experiment_design}}
{% endif %}

**写作规则**：
1. 开头用一段话概述整体架构
2. 按模块依次描述，每个核心模块独立成小节
3. 公式使用 <formula>...</formula> 标记
4. 引用使用 <citation>["keyword1", "keyword2"]</citation> 标记
5. 核心模块的设计选择应给出理由（为什么这样做而非那样做）
6. 避免重复描述标准方法，只需说明在本研究中的适配

请使用学术英语撰写，Markdown格式。直接给出内容：
