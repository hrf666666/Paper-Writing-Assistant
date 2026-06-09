# 输出有效性 + 完整度评价报告 (v9.0)

**对标**: IEEE TCSVT

## L1: 格式有效性

- 总分: 84/100

- md_exists: True
- md_size_kb: 68.3
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
- tex_cite_count: 32
- tex_has_citations: True
- tex_table_count: 1
- tex_has_tables: False
- tex_figure_count: 0
- tex_has_figures: False
- tex_no_placeholder: True
- tex_no_chinese: True
- tex_chinese_chars: 0
- bib_exists: True
- bib_entries: 42
- bib_min_entries: True
- pdf_exists: True
- pdf_size_kb: 158.2
- pdf_min_size: True
- figures_dir_exists: False
- figure_files_count: 0
- figures_min: False
- compile_log_exists: True
- compile_errors: 1
- compile_success: False

## L2: 内容完整度

- 总分: 83/100
- 章节覆盖: 5/5
- 总词数: 9919
- 引用数: 32

## L3: 学术质量（TCSVT 审稿模拟）

- 总分: 54.4/100

**审稿建议**: major_revision

**与 TCSVT 标准的关键差距:**

- Mathematical formalization: Core physical model (three-layer decomposition, mask generation, dual-branch routing) must be expressed in proper equation environments with variable definitions — currently absent from the visible source.
- Experimental rigor: Missing BadPix/MSE metrics, absence of visible ablation studies with statistical significance tests, and likely insufficient SOTA comparison breadth for TCSVT standards.
- Reference coverage: TCSVT requires comprehensive literature coverage (50+ references typical); the visible citation density suggests significant gaps in covering recent LF depth estimation and non-Lambertian modeling literature.
- The duplicated contribution lists and truncated markboth header indicate the manuscript was not carefully proofread before submission, raising concerns about overall experimental and methodological diligence.

## 总体评价

- **评级**: B
- L1=84 L2=83 L3=54.4