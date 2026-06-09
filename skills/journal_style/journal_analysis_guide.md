# Journal Style Analysis Guide

## Purpose
This guide instructs the LLM on how to analyze papers from a target journal to extract journal-specific writing patterns.

## Analysis Dimensions

### L7: Content Pattern — 内容编排模式
For each major section, analyze:
- **Opening style**: How does the section begin? (problem statement, background, overview)
- **Subsection organization**: What is the logical order of subsections?
- **Transition patterns**: How do subsections connect?
- **Closing style**: How does the section end? (summary, bridge to next section, open questions)

### L8: Argument Rhythm — 论证节奏
Analyze the placement patterns:
- Where are figures placed relative to the text that discusses them?
- Where are tables placed? Before or after the discussion?
- How dense are citations? Clustered or evenly spread?
- What is the typical paragraph length? Does it vary by section?

### L9: Depth Gradient — 深度梯度
For each subsection, classify its depth:
- **full_derivation**: Complete mathematical derivation with proofs
- **key_formulas_only**: Important formulas stated without full derivation
- **overview**: High-level description without mathematical detail
- **brief**: 1-2 sentences mentioning the concept

Look for patterns: Does this journal consistently give full derivations for methodology but brief overviews for experiments? Or vice versa?

### L10: Figure Preference — 图片风格偏好
Analyze the figures:
- **Architecture diagrams**: Detailed with all components, or clean flowcharts with only key modules?
- **Color scheme**: Vibrant multi-color, muted professional tones, or blue-dominant?
- **Annotations**: Heavy labeling or minimal text?
- **Layout**: Horizontal data flow, vertical pipeline, or grid comparison?
- **Size**: Figures tend to be full-page-width or single-column?

### L11: Content Emphasis — 内容侧重点
Identify what this journal values most:
- **Theory**: Is mathematical rigor the primary focus?
- **System**: Is implementation detail and system design the focus?
- **Experiments**: Are extensive comparisons and ablations the focus?
- **Application**: Is real-world applicability the focus?

Also identify:
- How is novelty presented? (explicit claims, subtle integration, comparison-driven)
- What gets the most page space? (methodology, experiments, or related work)

### L12: Journal Red Flags
Identify patterns that are consistently ABSENT from papers in this journal:
- Writing styles that this journal never uses
- Section structures that this journal never employs
- Presentation approaches that this journal avoids

## Important Notes
- Focus on PATTERNS across the paper, not isolated examples
- Distinguish between "this paper's style" and "this journal's style"
- When in doubt, prefer patterns that appear in multiple sections
- Be specific in descriptions (not just "detailed" but "includes formal problem statement, 3 lemmas, and algorithm pseudocode")
