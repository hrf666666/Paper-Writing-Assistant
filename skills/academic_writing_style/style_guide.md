# IEEE Transactions 学术写作风格指导

## 1. 词汇规范 (Lexical Standards)

### 1.1 禁止使用的 AI 风格词汇 (Banned AI-flavored Words)

以下词汇在 IEEE Transactions 顶刊中极少使用，应避免：

| 禁止词汇 | 问题 | 替代表达 |
|---------|------|---------|
| revolutionize | 过度夸张，营销用语 | transform, advance, improve |
| remarkably | 过度修饰，缺乏精确性 | significantly, substantially, notably |
| remarkable | 过度修饰，缺乏精确性 | significant, notable, considerable |
| seamlessly | 模糊不清，非技术术语 | effectively, efficiently, successfully |
| fundamentally | 夸大其词 | substantially, critically, essentially |
| unprecedented | 无法验证的绝对声明 | notable, distinctive, advanced |
| groundbreaking | 营销用语，非学术语言 | innovative, novel, advanced |
| revolutionary | 夸大其词 | advanced, improved, enhanced |
| paving the way | 陈词滥调 | enabling, facilitating, supporting |
| tremendous | 模糊的强度词 | considerable, substantial, significant |
| immense | 模糊的强度词 | substantial, considerable, extensive |
| game-changing | 营销用语 | transformative, impactful, significant |
| crucial | 过度使用，缺乏精确性 | important, essential, critical |
| vital | 过度使用 | important, necessary, essential |
| pivotal | 过度使用 | important, key, central |
| drastically | 过度夸张 | significantly, considerably, substantially |
| drastically | 过度夸张 | significantly, considerably, substantially |

### 1.2 推荐使用的学术词汇 (Preferred Academic Vocabulary)

**描述改进/提升**：improves, enhances, increases, reduces, decreases, achieves, demonstrates, yields

**描述方法特点**：employs, utilizes, leverages, integrates, combines, incorporates

**描述实验结果**：demonstrates, shows, indicates, reveals, confirms, validates

**描述贡献**：proposes, presents, introduces, develops, formulates, establishes

### 1.3 P5 清理规则 (Always Remove Patterns)

以下句式在 IEEE Transactions 中应**始终删除或重写**（来自 journal-adapt P5 规则）：

| 禁止句式 | 问题 | 替代策略 |
|---------|------|---------|
| "This paper explores..." | 空洞意图声明 | 直接陈述发现："This paper demonstrates..." |
| "In this study, we aim to..." | 意图而非结果 | "We propose X that achieves Y" |
| "It is worth noting that..." | 填充词 | 直接陈述事实 |
| "It should be noted that..." | 填充词 | 直接陈述事实 |
| "Furthermore," / "Moreover," / "Additionally," (作为空洞过渡) | 无信息量的连接词 | 使用结构性过渡或省略 |
| "contributes to the growing literature on..." | 空洞贡献声明 | 具体说明贡献内容 |
| "Future research should explore..." | 泛泛而谈 | 提出具体研究方向 |
| "Taken together, these findings suggest..." | 冗余总结 | 直接陈述含义 |
| "Our results highlight the importance of..." | 过度强调 | 陈述具体结果 |
| "To the best of our knowledge..." | 无法验证的声明 | 省略或直接陈述 |
| "This is the first study to..." | 绝对声明 | "Unlike prior work, we..." |
| "We propose a novel..." | "novel" 作为自我描述 | "We propose X that..." |
| "State-of-the-art performance" (结果前自述) | 未验证的声明 | 让数据说话 |
| "Our method is simple yet effective." | 空洞自我评价 | 描述具体设计选择 |
| "Extensive experiments demonstrate..." | 空洞修饰 | "Experiments on X datasets show..." |
| "We leave X for future work." (无具体方向) | 泛泛而谈 | 提出具体未来方向 |

## 2. 句式结构 (Sentence Structure)

### 2.1 括号使用规范

**原则**：括号内容应整合到句子中，而非作为补充说明

- 括号长度限制：<20 词
- 长括号内容应改为独立句子或 which/that 从句

### 2.2 破折号使用规范

IEEE Transactions 极少使用破折号：
- 避免使用破折号引入补充说明
- 替代：使用逗号、分号或独立句子

### 2.3 句子长度控制

- 理想句长：20-30 词/句
- 最大句长：不超过 40 词

## 3. 段落组织 (Paragraph Organization)

### 3.1 段落结构 (TEEL)

- **T**opic sentence：主题句（1 句）
- **E**xplanation：解释/展开（2-4 句）
- **E**vidence：证据/数据支撑（1-2 句）
- **L**ink：连接句/过渡句（1 句，可选）

### 3.2 段落长度

- 理想段长：100-200 词
- 最大段长：不超过 250 词

## 4. 时态规范 (Tense Conventions)

| 章节 | 时态 | 示例 |
|------|------|------|
| Introduction - 问题陈述 | 现在时 | Light field depth estimation remains challenging... |
| Introduction - 本文方法 | 现在时 | This paper proposes... |
| Related Work - 已有方法 | 现在完成时/过去时 | Several studies have investigated... |
| Methodology - 方法描述 | 现在时 | The network employs... |
| Experiments - 实验设置 | 过去时 | We trained the model for 100 epochs... |
| Experiments - 结果描述 | 过去时 | The proposed method achieved... |
| Conclusion - 贡献总结 | 现在时 | This work presents... |

## 5. 各章节文法要求 (Chapter-specific Conventions)

### 5.1 Introduction

**必须包含**：
1. 研究背景与动机（1-2 段）
2. 现有方法局限性（1 段）
3. 本文方法概述（1 段）
4. 主要贡献列表（3-4 点）
5. 论文组织结构（1 段，可选）

**禁止**：
- 过度夸大问题严重性
- 使用"first"、"novel"等声明性词汇（除非确实首创）

### 5.2 Related Work

**组织结构**：
- 按方法类别分组（而非按时间或作者）
- 每个类别 1-2 段
- 最后一段总结现有方法不足

### 5.3 Methodology

**结构要求**：
1. 总体架构概述（1 段 + 架构图）
2. 各子模块详细描述（每节 2-4 段）
3. 损失函数/优化目标（1-2 段）

### 5.4 Experiments

**必须包含**：
1. 数据集描述（1 段 + 表格）
2. 实现细节（1 段）
3. 对比方法（1 段）
4. 主实验结果（2-3 段 + 表格/图）
5. 消融实验（2-3 段 + 表格/图）

### 5.5 Conclusion

**结构要求**：
1. 问题重述（1 句）
2. 方法总结（2-3 句）
3. 关键结果（1-2 句，含数字）
4. 贡献总结（1-2 句）
5. 未来工作（1-2 句，可选）

**禁止**：
- 引入新方法/新结果
- 重复 Abstract 内容

## 6. 引用规范 (Citation Standards)

### 6.1 引用密度

- Introduction：5-10 篇
- Related Work：15-30 篇
- Methodology：3-8 篇
- Experiments：5-10 篇
- Conclusion：0-2 篇

### 6.2 引用格式

- IEEE 格式：[1], [2]-[5], [7], [9]-[11]
- 避免：[1,2,3,4,5] → 改为 [1]-[5]

## 7. ML/CV/NLP 专用规范 (IEEE Trans 场景适配)

### 7.1 Abstract 规范 (150-250 词)

**结构**：problem → limitation of prior work → proposed method → key results (with numbers) → significance

**必须包含**：
- 至少 1 个具体指标结果（e.g., "achieves 87.3% accuracy on X benchmark"）
- 方法/模型名称（如有）
- 过去时描述实验，现在时描述方法声明

**禁止**：
- 使用 "novel", "innovative", "state-of-the-art" 作为自我描述
- 开篇 "Deep learning has revolutionized..."

### 7.2 Introduction 规范

**结构**：problem motivation → limitations of existing approaches → your approach (high-level) → contributions (bulleted list) → paper structure

**贡献列表**：
- 最多 3 项
- 每项是具体可验证的声明
- 陈述为事实而非意图："We propose X that achieves Y" 而非 "We aim to address Z"

**禁止**：
- 开篇 "Deep learning has revolutionized..."
- 列出 5+ 贡献（削弱所有贡献）
- 承诺论文末尾未交付的结果

### 7.3 Related Work 规范

- 按方法/技术组织，而非时间顺序
- 每组相关工作：他们做了什么 + 他们不能做什么 + 你的方法如何不同
- 不要贬低前人工作，展示你充分理解后再指出局限性
- 引用密度：每个声明引用最相关的 3-5 篇，而非 10+ 篇

### 7.4 Method 规范

- 先描述直觉，再形式化
- 期望有 1 张展示整体架构/流程的图
- 首次使用前定义所有符号，全文保持符号一致性
- 算法伪代码：使用标准格式，编号所有行，文中引用行号
- 证明非显而易见的设计选择："We use X instead of Y because..."

### 7.5 Experiments 规范

**结构**：experimental setup → main results → ablation studies → analysis

**Setup 必须包含**：
- 数据集、评估指标、基线方法
- 实现细节（优化器、学习率、硬件、随机种子）

**Main results**：
- 包含所有基线的表格
- 加粗你的最佳结果
- 如适用，注明统计显著性

**Ablation**：
- 每次移除一个组件
- 每个消融测试一个设计决策

**禁止**：
- 仅报告准确率（包含相关次要指标）
- 仅挑选定性示例而无定量支持
- 省略超参数设置（阻碍可复现性）

### 7.6 Conclusion 规范

- 2-3 句总结贡献
- 诚实的局限性：方法无法处理什么、依赖什么假设
- 未来工作：1 个具体方向，而非愿望清单

## 8. 常见错误清单 (Common Error Checklist)

### 8.1 语言错误

- [ ] 使用 AI 风格词汇（remarkably, seamlessly, fundamentally 等）
- [ ] 长括号补充说明（>20 词）
- [ ] 破折号引入补充说明
- [ ] 口语化连接词（so, plus, besides）
- [ ] 第一人称单数（I propose）
- [ ] 过度使用被动语态（>60% 句子）

### 8.2 结构错误

- [ ] Introduction 缺少贡献列表
- [ ] Related Work 按时间而非类别组织
- [ ] Methodology 包含实现细节
- [ ] Experiments 缺少消融实验
- [ ] Conclusion 引入新内容

### 8.3 数据错误

- [ ] 结果未量化（无具体数字）
- [ ] 对比不公平（不同设置/数据）
- [ ] 失败案例未分析
- [ ] 引用未验证（引用不存在/不相关文献）
