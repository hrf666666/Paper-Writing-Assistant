# 输出有效性 + 完整度评价报告 (v9.0)

**对标**: IEEE TCSVT

## L1: 格式有效性

- 总分: 100/100

- md_exists: True
- md_size_kb: 76.9
- md_min_size: True
- tex_exists: True
- tex_has_ieeetran: True
- tex_has_lettersize: True
- tex_has_abstract: True
- tex_has_keywords: True
- tex_has_markboth: True
- tex_equation_count: 22
- tex_has_display_math: True
- tex_no_markdown: True
- tex_md_residuals: 0
- tex_cite_count: 10
- tex_has_citations: False
- tex_table_count: 2
- tex_has_tables: True
- tex_figure_count: 1
- tex_has_figures: True
- tex_no_placeholder: True
- tex_no_chinese: True
- tex_chinese_chars: 0
- bib_exists: True
- bib_entries: 36
- bib_min_entries: True
- pdf_exists: True
- pdf_size_kb: 171.3
- pdf_min_size: True
- figures_dir_exists: True
- figure_files_count: 8
- figures_min: True
- compile_log_exists: True
- compile_errors: 80
- compile_success: False

## L2: 内容完整度

- 总分: 66/100
- 章节覆盖: 5/5
- 总词数: 11294
- 引用数: 10

## L3: 学术质量（TCSVT 审稿模拟）

- 总分: 54/100

**审稿建议**: reject

**与 TCSVT 标准的关键差距:**

- Citation integrity failure: Mismatched citation keys (he2016→LF imaging, ronneberger2015→Williem et al., dosovitskiy2021→Shin et al.) indicate either placeholder bibliography or academic carelessness. TCSVT requires accurate, complete referencing (typically 40-60+ citations for full-length papers). Only 5 visible citations is grossly insufficient.
- Structural incompleteness: The paper has duplicate related-work sections (content before Section II + empty stubs under Section II), a truncated \markboth header, and no visible experimental section within 24K characters. This suggests the manuscript was not ready for submission.
- Insufficient experimental substantiation: Despite claims of '130+ experimental trials across 16 directions,' no figures, tables, ablation studies, or BadPix metrics are present in the source. TCSVT requires comprehensive empirical validation across multiple datasets with SOTA comparisons — none is visible here.

## 总体评价

- **评级**: C
- L1=100 L2=66 L3=54