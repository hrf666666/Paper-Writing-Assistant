# 输出有效性 + 完整度评价报告 (v9.0)

**对标**: IEEE TCSVT

## L1: 格式有效性

- 总分: 92/100

- md_exists: True
- md_size_kb: 55.8
- md_min_size: True
- tex_exists: True
- tex_has_ieeetran: True
- tex_has_lettersize: True
- tex_has_abstract: True
- tex_has_keywords: True
- tex_has_markboth: True
- tex_equation_count: 6
- tex_has_display_math: True
- tex_no_markdown: True
- tex_md_residuals: 0
- tex_cite_count: 31
- tex_has_citations: True
- tex_table_count: 0
- tex_has_tables: False
- tex_figure_count: 0
- tex_has_figures: False
- tex_no_placeholder: True
- tex_no_chinese: True
- tex_chinese_chars: 0
- bib_exists: True
- bib_entries: 7
- bib_min_entries: False
- pdf_exists: True
- pdf_size_kb: 125.2
- pdf_min_size: True
- figures_dir_exists: True
- figure_files_count: 10
- figures_min: True
- compile_log_exists: True
- compile_errors: 15
- compile_success: False

## L2: 内容完整度

- 总分: 83/100
- 章节覆盖: 5/5
- 总词数: 8141
- 引用数: 31

## L3: 学术质量（TCSVT 审稿模拟）

- 总分: 45.5/100

**审稿建议**: reject

**与 TCSVT 标准的关键差距:**

- Citation integrity falls far below TCSVT standards: fewer than 10 distinct citation keys are visible, multiple references are clearly misattributed (e.g., vaswani2017 for LFT), and numerous factual claims lack any citation — this alone warrants rejection as it indicates an incomplete draft
- Mathematical formalization is inadequate for a TCSVT theory-methods paper: the core physical model lacks proper equation environments, no derivation or proof of the decomposition's validity is provided, and the 'three-layer decomposition' is essentially a first-order Taylor expansion presented without justification for why it captures material properties in the residual
- No experimental figures, tables, or quantitative comparison tables are visible in the source code — while the text mentions datasets (HCInew, UrbanLF-Syn) and metrics (MAE), there are no \begin{figure}, \begin{table}, or result environments, making it impossible to verify the claimed improvements or assess BadPix/Q25 metrics standard in LF depth estimation literature

## 总体评价

- **评级**: C
- L1=92 L2=83 L3=45.5