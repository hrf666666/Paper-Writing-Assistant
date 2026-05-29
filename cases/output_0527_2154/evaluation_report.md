# 输出有效性 + 完整度评价报告 (v9.0)

**对标**: IEEE TCSVT

## L1: 格式有效性

- 总分: 84/100

- md_exists: True
- md_size_kb: 71.2
- md_min_size: True
- tex_exists: True
- tex_has_ieeetran: True
- tex_has_lettersize: True
- tex_has_abstract: True
- tex_has_keywords: True
- tex_has_markboth: True
- tex_equation_count: 286
- tex_has_display_math: True
- tex_no_markdown: True
- tex_md_residuals: 0
- tex_cite_count: 28
- tex_has_citations: True
- tex_table_count: 1
- tex_has_tables: False
- tex_figure_count: 1
- tex_has_figures: True
- tex_no_placeholder: True
- tex_no_chinese: False
- tex_chinese_chars: 261
- bib_exists: True
- bib_entries: 43
- bib_min_entries: True
- pdf_exists: True
- pdf_size_kb: 149.2
- pdf_min_size: True
- figures_dir_exists: True
- figure_files_count: 1
- figures_min: False
- compile_log_exists: True
- compile_errors: 191
- compile_success: False

## L2: 内容完整度

- 总分: 83/100
- 章节覆盖: 5/5
- 总词数: 11242
- 引用数: 28

## L3: 学术质量（TCSVT 审稿模拟）

- 总分: 39.8/100

**审稿建议**: reject

**与 TCSVT 标准的关键差距:**

- The titled 'dual-mask physical model' lacks any formal mathematical definition in the visible manuscript — no reflectance equations, no BRDF decomposition, no loss function formalization. TCSVT requires rigorous signal-processing or circuit-system-level mathematical grounding, which is entirely absent.
- The claimed 'physical model' contributions are unsupported by equations; the paper instead devotes numbered equations to trivial scalar values (percentages and dimensions). This fundamentally fails TCSVT's methodological rigor standards.
- No experimental evidence is presented in the source — no quantitative comparison tables, no ablation studies, no BadPix metrics, and no visual result figures. The abstract claims (26% MAE reduction, 37%/41% domain improvements) cannot be verified against any presented data.

## 总体评价

- **评级**: C
- L1=84 L2=83 L3=39.8