# Phase 8.5 PDF 视觉审查报告

**审查方式**: PyMuPDF 文本提取 + .tex 源码结构分析 + IEEE 模板对比  
**审查日期**: 2026-05-27 23:50  
**对比模板**: `latex_templates/IEEE_article/bare_jrnl_new_sample4.tex`  
**生成文件**: `output/full_paper.pdf` (15 页)

---

## 问题汇总 (共 10 类 20+ 个问题)

### ❌ P1. TikZ 架构图中文字符乱码 [严重]

**位置**: 第 5 页，TikZ 架构图 (L134-L198)

**现象**: PyMuPDF 提取到 15 处 `￿` (Unicode 替换字符)，31 个中文/乱码片段

**根因**: TikZ 节点中使用了中文标签（如"节点定义"、"输入"、"并行分支模块"），但 XeLaTeX 编译时字体不支持这些字符

**对比**: IEEE 模板中 TikZ/figure 仅使用英文标注

**修复**: `latex_converter.py` 应将 TikZ 图中的中文替换为英文，或在 `\begin{tikzpicture}` 前设置中文字体

---

### ❌ P2. 表格溢出到后续页面 [严重]

**位置**: 
- TABLE I (L84-L101): 7 列 `p{0.13\textwidth}` → 溢出到第 13 页
- TABLE II (L391-L406): 8 列 `p{0.13\textwidth}` → 溢出到第 14-15 页

**现象**: 
- 第 13 页仅显示 TABLE I 的部分内容（表格每列都折行，高度超出单页）
- 第 14-15 页显示 TABLE II（内容与 TABLE III 重复）

**根因**: 
1. 列宽 `p{0.13\textwidth}` × 7 = 0.91\textwidth，但内容过长导致大量折行
2. 表格使用了 `table*[!t]` 浮动体，LaTeX 将表格推到页面底部或末尾
3. 第二个表格 TABLE III 内容与 TABLE II 几乎相同（重复）

**对比**: IEEE 模板中表格简洁，列数 ≤5，使用 `|c||c|` 简单格式

---

### ❌ P3. `\IEEEPARstart` 缺失 [中等]

**位置**: Introduction 章节开头

**现象**: Introduction 直接以 "Light field depth estimation..." 开始，没有首字母放大的 `\IEEEPARstart{T}{his}` 格式

**对比**: IEEE 模板明确使用 `\IEEEPARstart{T}{his} file is intended...`

**修复**: `latex_converter.py` 在 `\section{Introduction}` 后的第一段自动添加 `\IEEEPARstart`

---

### ❌ P4. `\textbf{Table I: ...}` 错误嵌入正文 [严重]

**位置**: L82 附近

**现象**: `\textbf{Table I: Comparison of Representative Light Field Depth Estimation Methods}` 直接出现在正文中，而非 `\begin{table}` 环境内

**根因**: LLM 生成的 Markdown 表格标记未被正确转换为 LaTeX table 环境

**修复**: `latex_converter.py` 应检测 `\textbf{Table N:` 模式并转换为 `\begin{table}` 环境

---

### ❌ P5. 章节编号重复/错误 [中等]

**位置**: Experiments 章节

**现象**: 
```latex
\section{4. Experiments}
\subsubsection{4.1. Datasets}
\paragraph{4.1.1. Dataset Descriptions.}
```

**问题**: 
1. `\section` 已自动编号，不应再写 "4."
2. `\subsubsection` 跳过了 `\subsection` 层级
3. `\paragraph` 中包含了手动编号 "4.1.1."

**对比**: IEEE 模板使用 `\section{}` → `\subsection{}` → `\subsubsection{}`，不手动编号

---

### ❌ P6. 表格 caption 全部相同 [中等]

**位置**: 两个 `table*` 环境

**现象**: 两个表格的 caption 都是 `\caption{Comparison of performance metrics.}`

**根因**: `latex_converter.py` 中表格转换函数硬编码了 caption

```python
latex_table += '\\caption{Comparison of performance metrics.}\n'
```

**修复**: 从表格上下文提取合适的 caption，或按序号区分

---

### ❌ P7. 表格 label 全部相同 [中等]

**位置**: 两个 `table*` 环境

**现象**: 两个表格的 label 都是 `\label{tab:comparison}`

**根因**: `latex_converter.py` 硬编码

**修复**: 按序号递增 `tab:comparison_1`, `tab:comparison_2`

---

### ❌ P8. 图表数量严重不足 [中等]

**现状**: 1 张图 (TikZ 架构图), 2 个表格

**对比**: IEEE 模板示例有 2 张图 + 1 表 + 1 算法，实际论文通常 5-10 图 + 3-5 表

**缺失内容**:
- ❌ 实验结果对比图 (MAE 柱状图/折线图)
- ❌ 深度图可视化对比 (预测 vs GT)
- ❌ 消融实验结果表
- ❌ 算法伪代码 (algorithm 环境)
- ❌ EPI 示意图

---

### ❌ P9. TikZ 图缺少英文标签 [中等]

**位置**: 第 5 页架构图

**现象**: TikZ 节点中包含中文 "EPI" 等混合标注，但大部分标签在 PDF 中渲染为 `￿` (不可见)

**根因**: `figure_generator.py` 生成的 TikZ 代码使用了中文字符，但编译环境缺少中文字体支持

**修复**: 
1. 短期: 所有 TikZ 节点标签改为英文
2. 长期: 在 LaTeX 模板中添加 `\usepackage{ctex}` 支持中文

---

### ❌ P10. 重复表格 (TABLE II ≈ TABLE III) [严重]

**位置**: 第 13-15 页

**现象**: 第 14 页 TABLE II 和第 15 页 TABLE III 内容几乎相同（都是 Dataset Name/Scene Type/Angular Res./Spatial Res. 等列）

**根因**: `_deduplicate_sections` 只检测 `\section` 标题重复，未检测 `\begin{table}` 内容重复

---

## 与 IEEE 模板对比总览

| 检查项 | IEEE 模板 | 生成论文 | 状态 |
|--------|-----------|----------|------|
| **双栏排版** | ✅ journal 模式 | ✅ 双栏 | OK |
| **标题格式** | ✅ 居中、大小写 | ✅ 正确 | OK |
| **作者信息** | ✅ \thanks + \markboth | ✅ 有 | OK |
| **首字母放大** | ✅ \IEEEPARstart | ❌ 缺失 | 问题 |
| **摘要格式** | ✅ \begin{abstract} | ✅ 有 | OK |
| **关键词** | ✅ \begin{IEEEkeywords} | ❌ 未检查 | 待验证 |
| **引用格式** | ✅ \cite{ref1} [1] | ✅ 43 个引用 | OK |
| **公式编号** | ✅ \label + \eqref | ✅ 15 个公式 | OK |
| **表格格式** | ✅ \begin{table} + caption 在前 | ❌ caption 重复/表格溢出 | 问题 |
| **图片格式** | ✅ \begin{figure} + \includegraphics | ❌ 仅 1 张(TikZ 乱码) | 问题 |
| **算法环境** | ✅ \begin{algorithm} | ❌ 无 | 缺失 |
| **章节编号** | ✅ 自动编号 | ❌ 手动编号 4. / 4.1. | 问题 |
| **参考文献** | ✅ \begin{thebibliography} | ✅ BibTeX 51 条 | OK |
| **字体/行距** | ✅ 10pt 两栏 | ✅ 基本正常 | OK |
| **页眉** | ✅ \markboth | ✅ 有 | OK |

---

## 优先级排序

| 优先级 | 问题 | 影响 |
|--------|------|------|
| **P0** | P2: 表格溢出占 3 页 | 15 页中 3 页是溢出表格 |
| **P0** | P10: 重复表格 | 第 14-15 页内容完全重复 |
| **P0** | P1: TikZ 中文乱码 | 架构图不可读 |
| **P1** | P4: \textbf{Table} 嵌入正文 | 表格标记格式错误 |
| **P1** | P5: 章节编号错误 | 不符合 IEEE 规范 |
| **P1** | P8: 图表数量不足 | 学术论文基本要求 |
| **P2** | P3: \IEEEPARstart 缺失 | IEEE 风格规范 |
| **P2** | P6/P7: caption/label 重复 | 引用混乱 |
| **P2** | P9: TikZ 标签问题 | 图表质量 |

---

## 根因归类

1. **`latex_converter.py` 问题** (P3, P4, P5, P6, P7): 转换逻辑缺陷
2. **`figure_generator.py` 问题** (P1, P9): TikZ 代码中文问题
3. **LLM 生成质量问题** (P4, P5): 手动编号、表格嵌入正文
4. **去重逻辑缺失** (P10): 只去重 section 不去重 table

---

**报告生成时间**: 2026-05-27 23:55
