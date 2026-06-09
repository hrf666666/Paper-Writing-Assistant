# Content Strategy Template

## Purpose
This template guides the LLM in planning content strategy for each chapter before writing begins.

## Strategy Dimensions

### Focus Areas
For each chapter, identify the 2-3 topics that must receive the most attention.
These should be derived from:
1. The paper's innovation points
2. The target journal's content emphasis
3. The motivation thread anchors

### Depth Map
For each subsection, specify the depth level:
- **deep**: Full derivation, extensive discussion, multiple examples
- **moderate**: Key points with supporting evidence
- **brief**: Overview or summary level
- **skip**: Can be omitted or merged with another section

### Innovation Allocation
Map each innovation point to the chapter(s) where it should be prominently featured:
- **primary**: This chapter is the main showcase for this innovation
- **supporting**: This chapter references this innovation as supporting evidence
- **mention**: This chapter briefly mentions this innovation for context

### Must Include
Specific content elements that MUST appear in this chapter:
- Data points, comparisons, or analyses
- Figures or tables
- References to specific prior work
- Connections to other chapters

### Should Avoid
Content that should NOT appear in this chapter:
- Topics that belong in other chapters
- Excessive detail that would be better in supplementary material
- Methods or analyses that are not relevant to this paper's contributions

## Chapter-Specific Strategy Patterns

### Introduction Strategy
```
focus_areas: [问题重要性, 现有方法局限, 本文贡献]
depth_map: {背景: brief, 局限分析: moderate, 贡献: deep}
innovation_allocation: {创新点1: mention, 创新点2: mention, 创新点3: mention}
must_include: [至少1个具体数据支撑问题严重性, 清晰的gap statement]
should_avoid: [详细的方法描述, 大量引用（>10篇/段）]
```

### Methodology Strategy
```
focus_areas: [创新模块详细描述, 整体架构设计, 训练策略]
depth_map: {概述: brief, 创新模块: deep, 基础模块: moderate, 训练: brief}
innovation_allocation: {创新点1: primary, 创新点2: primary}
must_include: [完整公式推导, 模块间数据流说明, 与现有方法的差异对比]
should_avoid: [不必要的推导细节, 过度描述已有方法]
```

### Experiments Strategy
```
focus_areas: [主要对比实验, 消融实验, 可视化分析]
depth_map: {数据集: brief, 对比实验: deep, 消融实验: deep, 可视化: moderate}
innovation_allocation: {创新点1: supporting, 创新点2: supporting}
must_include: [完整的消融实验表格, 与SOTA的定量对比, 定性可视化]
should_avoid: [过度吹嘘结果, 回避分析负面结果]
```
