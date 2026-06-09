# 输出有效性 + 完整度评价报告 (v9.0)

**对标**: IEEE TCSVT

## L1: 格式有效性

- 总分: 92/100

- md_exists: True
- md_size_kb: 82.1
- md_min_size: True
- tex_exists: True
- tex_has_ieeetran: True
- tex_has_lettersize: True
- tex_has_abstract: True
- tex_has_keywords: True
- tex_has_markboth: True
- tex_equation_count: 27
- tex_has_display_math: True
- tex_no_markdown: True
- tex_md_residuals: 0
- tex_cite_count: 10
- tex_has_citations: False
- tex_table_count: 1
- tex_has_tables: False
- tex_figure_count: 2
- tex_has_figures: True
- tex_no_placeholder: True
- tex_no_chinese: True
- tex_chinese_chars: 0
- bib_exists: True
- bib_entries: 39
- bib_min_entries: True
- pdf_exists: True
- pdf_size_kb: 168.1
- pdf_min_size: True
- figures_dir_exists: True
- figure_files_count: 10
- figures_min: True
- compile_log_exists: True
- compile_errors: 97
- compile_success: False

## L2: 内容完整度

- 总分: 66/100
- 章节覆盖: 5/5
- 总词数: 11779
- 引用数: 10

## L3: 学术质量（TCSVT 审稿模拟）

- 总分: 46.3/100

**审稿建议**: reject

**与 TCSVT 标准的关键差距:**

- Citation integrity failure: Identical BibTeX keys (he2016, vaswani2017) are assigned to completely different author groups and papers. TCSVT requires accurate, verifiable references. With only ~3 unique visible citation keys and blatant misattribution, the paper falls far below the minimum scholarly standard for a top-tier IEEE journal.
- Insufficient methodological formalization: The lone mathematical contribution is an inline first-order linear decomposition lacking proper equation environments, theorem-style presentation, or convergence/complexity analysis. TCSVT papers on computational imaging must demonstrate rigorous algorithmic and mathematical depth commensurate with the claimed 'physical model'.
- No verifiable experimental evidence in the submitted source: Zero tables, zero figures with results, zero ablation studies, and zero BadPix metrics are present. TCSVT requires comprehensive experimental validation including multiple datasets, SOTA comparisons, ablation studies, and computational cost analysis — none of which can be confirmed from the manuscript source.

## 总体评价

- **评级**: C
- L1=92 L2=66 L3=46.3