# paper-writing-assistant v9.0 详细升级计划

> 设计时间: 2026-05-27
> 目标: 从"能生成论文"到"能生成顶刊水平论文"，支持 .md / .tex / .pdf 三格式输出
> 测试标准: 输出有效性和完整度量化评价

---

## 全局架构变更

```
v8.0 架构（当前）:
  Phase 0 → 0.5 → 0.6 → 1~5 → 6 → 6.5 → 7
  单次大prompt生成 → 章节级质量门控 → 输出

v9.0 架构（目标）:
  Phase 0 [分析]  ← 增强创新点验证
  Phase 0.5 [规划] ← 增强章节锚定
  Phase 0.6 [动机] ← 不变
  Phase 0.7 [数据源] ← 新增：实验数据统一
  Phase 1~5 [生成] ← 改为分段生成
  Phase 6 [审查] ← 不变
  Phase 6.5 [审计] ← 修复bug
  Phase 7 [后处理] ← 增强：引用→BibTeX
  Phase 7.5 [全局打磨] ← 新增
  Phase 8 [输出] ← 新增：md + tex + pdf + 评价
  Phase 9 [自评] ← 新增：输出有效性+完整度评价
```

---

## 升级项详细设计（按依赖顺序）

### U1. 实验数据单一数据源（新增 Phase 0.7）

**问题**: 当前 `project_analyzer.extract_experiment_design()` 提取的数据可能与代码实际运行结果不一致，导致 Abstract 和 Experiments 数值矛盾（MAE 0.125 vs 0.095）。

**文件**: 新增 `tools/data_source_manager.py`

**设计**:

```python
class DataSourceManager:
    """
    实验数据单一数据源（Single Source of Truth）
    
    数据优先级：
    1. 消融实验实际运行结果 (ablation_results.json)
    2. 工程目录中的训练日志/报告 (report.pdf → MCP web-reader 提取)
    3. project_analyzer 提取的结构化数据
    4. [DATA-PLACEHOLDER] 标记（由用户填写）
    """
    
    def build_unified_results(self, project_path, project_data):
        """
        构建统一实验数据文件: output/unified_results.json
        
        结构:
        {
            "datasets": [{"name": "KITTI", "split": "test", "scenes": 15}],
            "metrics": [
                {"name": "MAE", "unit": "mm", "direction": "lower"},
                {"name": "RMSE", "unit": "mm", "direction": "lower"},
                {"name": "BadPix 0.01", "unit": "%", "direction": "lower"}
            ],
            "main_results": [
                {"method": "Ours", "dataset": "KITTI", "values": {"MAE": 0.125, ...}},
                {"method": "EPI_baseline", "dataset": "KITTI", "values": {"MAE": 0.411, ...}},
                ...
            ],
            "ablation_results": [
                {"name": "w/o medium_mask", "dataset": "KITTI", "values": {"MAE": 0.208}},
                ...
            ],
            "non_lambertian_analysis": {
                "overall_MAE": 0.125,
                "non_lambertian_MAE": 0.208,
                "improvement_pct": 49.4
            },
            "source": "report_extraction",  # 标记数据来源
            "confidence": "high"             # high/medium/placeholder
        }
        """
    
    def get_value(self, key_path: str) -> Any:
        """从统一数据源读取值，禁止 LLM 编造"""
    
    def inject_data_constraint(self, prompt: str) -> str:
        """在 prompt 中注入数据约束，禁止 LLM 修改数字"""
```

**集成点**:
- `loop.py` Phase 0.7 调用 `DataSourceManager.build_unified_results()`
- `ch4_experiments.py` 和 `ch5_conclusion.py` 生成时从 `unified_results.json` 读取数据
- Abstract 生成时从 `unified_results.json` 读取关键指标
- 数据注入 prompt 模板: "以下是实验的真实数据，你**必须**使用这些数据，**禁止修改任何数字**:\n{data_block}"

**测试**:
- 单元测试: 验证数据提取逻辑、占位符标记
- 集成测试: 确认所有章节数据一致

---

### U2. 创新点验证与递进设计（增强 Phase 0）

**问题**: 当前创新点由 LLM 一次性提取，可能泛化（如"提出了一种新的损失函数"），缺乏新颖性验证和递进关系。

**文件**: 新增 `tools/innovation_verifier.py`

**设计**:

```python
class InnovationVerifier:
    """
    创新点三阶段验证
    
    Stage 1: 新颖性验证 — 搜索学术文献确认候选创新点是否已被提出
    Stage 2: 递进关系设计 — 确保3个创新点形成逻辑链
    Stage 3: 章节锚定 — 每个创新点映射到具体子节和实验
    """
    
    def verify_novelty(self, innovation_points: List[Dict]) -> List[Dict]:
        """
        Stage 1: 对每个创新点进行新颖性搜索
        
        流程:
        1. 从创新点提取搜索关键词
        2. MCP web-search → 百度学术 → Semantic Scholar 搜索
        3. LLM 判断搜索结果是否与候选创新点重叠
        4. 输出: novelty_score (0-1) + related_work_refs
        
        novelty_score < 0.3 的创新点标记为 "可能不新颖"，需要重新设计
        """
    
    def design_progression(self, innovation_points: List[Dict]) -> Dict:
        """
        Stage 2: 设计创新点的递进关系
        
        理想递进模式:
        点1: 问题定义/建模 — "我们发现现有方法忽略了X"
        点2: 方法创新 — "我们提出Y来解决X"
        点3: 验证/应用 — "我们在Z条件下验证了Y的有效性"
        
        LLM 构建:
        - 递进逻辑链 (点1→点2→点3 的因果/递进关系)
        - 贡献声明 (每个点对应一个明确的 contribution)
        - 故事线摘要 (3句话概括全文故事)
        """
    
    def anchor_to_sections(self, innovation_points: List[Dict], 
                           outline: Dict) -> Dict:
        """
        Stage 3: 将创新点锚定到具体章节
        
        输出 anchor_map:
        {
            "innovation_1": {
                "related_work_section": "2.1 Traditional Methods",
                "methodology_section": "3.2 Angular Frequency Analysis",
                "experiment_section": "4.3 Ablation: w/o frequency analysis",
                "contribution_statement": "We identify that..."
            },
            ...
        }
        
        写入 bounded_context 长期记忆，强制后续生成遵守
        """
```

**集成点**:
- `loop.py` Phase 0 完成后调用 `InnovationVerifier`
- `bounded_context.py` 新增 `set_anchor_map()`
- `structure_planner.py` 的 `_derive_subsections()` 读取 anchor_map
- `ch3_methodology.py` 和 `ch4_experiments.py` 读取 anchor_map 确保覆盖

---

### U3. 段落级生成与质量控制（重构 Phase 1~5）

**问题**: 当前每章一次大 prompt（~6000 token）生成，质量上限受限。段落可能缺少明确目的。

**文件**: 修改 `ch1_introduction.py` ~ `ch5_conclusion.py`，新增 `tools/paragraph_controller.py`

**设计**:

```python
class ParagraphController:
    """
    段落级生成控制器
    
    核心思路：
    - 每章先规划段落列表（每段有明确目的和要点）
    - 逐段生成，注入前文摘要保持连贯
    - 每段生成后做轻量检查（有目的？推进论点？与前文衔接？）
    """
    
    def plan_paragraphs(self, chapter_name: str, outline: Dict,
                        innovation_points: List, prev_chapters_summary: str,
                        anchor_map: Dict) -> List[Dict]:
        """
        规划段落列表
        
        输出:
        [
            {
                "index": 0,
                "purpose": "定义研究问题",
                "key_points": ["非Lambertian场景深度估计是开放问题", "现有方法在镜面反射区域完全失效"],
                "target_length": 120,  # 词数
                "must_include": ["EPI", "Lambertian assumption"],
                "anchor_to": "innovation_1",  # 关联的创新点
            },
            ...
        ]
        """
    
    def generate_paragraph(self, para_plan: Dict, prev_text: str,
                           chapter_context: str) -> str:
        """生成单个段落"""
    
    def check_paragraph(self, text: str, plan: Dict) -> Dict:
        """
        轻量段落检查（不调 LLM，纯规则）
        
        检查项:
        - 长度是否在目标范围内（±30%）
        - must_include 关键词是否出现
        - 是否有新的 [N] 引用（如果 plan 要求）
        - 是否有推进论点的信号词（however/furthermore/to address this）
        """
```

**各章节生成器改造**:

```python
# ch3_methodology.py 改造示意
def generate_methodology(project_data, ...):
    # 1. 读取 anchor_map，确定方法论子节与创新点对应
    # 2. 为每个子节规划段落
    # 3. 逐段生成
    # 4. 段落间添加过渡句
    
    para_ctrl = ParagraphController(api_client)
    paragraphs = para_ctrl.plan_paragraphs("Methodology", outline, ...)
    
    sections = []
    for section_plan in subsection_plans:
        paras = []
        for para_plan in section_plan.paragraphs:
            text = para_ctrl.generate_paragraph(para_plan, prev_text, ...)
            check = para_ctrl.check_paragraph(text, para_plan)
            if not check["passed"]:
                text = para_ctrl.regenerate_paragraph(para_plan, check["issues"])
            paras.append(text)
        sections.append(assemble_section(section_plan, paras))
```

---

### U4. BibTeX 引用生成（增强 Phase 7）

**问题**: `references.bib` 为空，`[N]` 格式引用未转为 `\cite{key}`。

**文件**: 修改 `citation_manager.py`、`latex_converter.py`，新增 `tools/bibtex_builder.py`

**设计**:

```python
class BibTeXBuilder:
    """
    从已验证的引用池生成 BibTeX 条目
    """
    
    def build_from_verified_citations(self, verified_citations: List[Dict]) -> str:
        """
        输入: CitationManager.verify() 的输出
        输出: 完整的 .bib 文件内容
        
        格式:
        @article{zhang2024dualmask,
            title={Dual-Mask Physical Model for Light Field Depth Estimation},
            author={Zhang, Wei and Li, Ming and ...},
            journal={IEEE TIP},
            year={2024},
            ...
        }
        
        cite_key 生成规则: 第一作者姓 + 年份 + 首词
        """
    
    def replace_numeric_with_cite(self, text: str, 
                                   citation_map: Dict[int, str]) -> str:
        """
        将 [1], [2] 替换为 \cite{zhang2024dual}
        [1,2] → \cite{zhang2024dual,li2023angular}
        [1-3] → \cite{zhang2024dual,li2023angular,wang2024frequency}
        """
```

**LaTeX 转换器增强**:
- `latex_converter.py` 新增 BibTeX 集成
- 模板中 `\bibliographystyle{IEEEtran}` + `\bibliography{references}`
- `\cite` 命令替换逻辑

---

### U5. PDF 生成管线（新增 Phase 8）

**问题**: 系统没有 PDF 生成能力。用户需手动编译 .tex。

**文件**: 新增 `tools/pdf_compiler.py`

**方案选择**（按优先级）:

| 方案 | 依赖 | 优点 | 缺点 |
|------|------|------|------|
| **A. Pandoc** | `pip install pypandoc` + 系统 pandoc | 从 Markdown 直接生成 PDF | 需要安装 pandoc + LaTeX 引擎 |
| **B. XeLaTeX** | texlive-xetex | 最高质量，中文支持 | 需要安装 ~2GB |
| **C. WeasyPrint** | `pip install weasyprint` | 轻量，纯 Python | LaTeX 公式支持差 |
| **D. 纯 Python** | `pip install fpdf2` + markdown | 零外部依赖 | 公式渲染困难 |

**推荐: A+B 组合**
- 安装 `pandoc` + `texlive-xetex`（~3GB）
- Pandoc: Markdown → PDF（快速通道，用系统 LaTeX 引擎）
- XeLaTeX: .tex → PDF（高质量通道，编译我们生成的 .tex）

```python
class PDFCompiler:
    """
    PDF 编译器
    
    两条路径:
    1. .tex → xelatex → .pdf  （高质量，使用生成的 LaTeX 文件）
    2. .md → pandoc → .pdf    （快速通道，备选）
    """
    
    def compile_latex(self, tex_path: str, output_dir: str) -> str:
        """
        XeLaTeX 编译
        
        流程:
        1. xelatex main.tex  (第一遍)
        2. bibtex main       (处理引用)
        3. xelatex main.tex  (第二遍，解决交叉引用)
        4. xelatex main.tex  (第三遍，确保稳定)
        
        错误处理:
        - 编译失败 → 解析 .log 找到错误行 → 自动修复常见问题 → 重试
        - 常见问题: 未定义的引用、缺少包、编码问题
        """
    
    def compile_pandoc(self, md_path: str, output_dir: str) -> str:
        """
        Pandoc 快速通道
        
        pandoc full_paper.md -o full_paper.pdf \
            --pdf-engine=xelatex \
            --template=ieee \
            -V geometry:margin=1in
        """
```

---

### U6. 全局打磨阶段（新增 Phase 7.5）

**问题**: 各章独立迭代，没有通读全文的全局优化。

**文件**: 新增 `tools/global_polisher.py`

**设计**:

```python
class GlobalPolisher:
    """
    全文通读打磨
    
    在所有章节完成、引用解析之后，输出生成之前执行。
    纯 LLM 驱动的全局优化，不修改章节内容，只做润色。
    """
    
    def polish(self, full_text: str, anchor_map: Dict, 
               unified_results: Dict) -> Dict:
        """
        全局打磨5个维度:
        
        1. 跨章节过渡: 检查每章结尾和下一章开头的过渡是否自然
        2. 术语统一: 同一概念是否全文用同一术语
        3. 符号统一: 数学符号是否全文一致
        4. 冗余消除: 跨章节重复的表述改为交叉引用
        5. 节奏优化: 篇幅是否均匀，是否有某节过长/过短
        
        输出:
        {
            "polished_text": "...",
            "changes": [
                {"type": "transition", "location": "§1→§2", "before": "...", "after": "..."},
                {"type": "terminology", "before": "dual-mask model", "after": "dual-mask physical model", "count": 5},
                ...
            ],
            "quality_delta": +3.5  # 质量提升预估
        }
        """
```

---

### U7. 输出有效性+完整度评价（新增 Phase 9）

**问题**: 当前没有对最终输出做系统性的有效性/完整度评价。

**文件**: 新增 `tools/output_evaluator.py`

**设计**:

```python
class OutputEvaluator:
    """
    输出有效性 + 完整度评价
    
    三层评价:
    L1: 格式有效性 — .md/.tex/.pdf 是否生成且可读
    L2: 内容完整度 — 结构、引用、公式、图表、数据是否完整
    L3: 学术质量 — LLM 驱动的多维度学术质量评价
    """
    
    # ── L1: 格式有效性 ──
    def eval_format_validity(self, output_dir: str) -> Dict:
        """
        检查:
        - .md 文件存在且非空且 > 5KB
        - .tex 文件存在且可编译（无致命错误）
        - .pdf 文件存在且页数 > 0
        - .bib 文件存在且有条目
        - .tex 中无残留 Markdown 语法（##, **, [N]等）
        - .tex 中 \cite{} 引用数量 > 0
        """
    
    # ── L2: 内容完整度 ──
    def eval_content_completeness(self, output_dir: str,
                                   outline: Dict, anchor_map: Dict,
                                   unified_results: Dict) -> Dict:
        """
        检查:
        - 5章是否完整（无 [TODO] / [PLACEHOLDER]）
        - 每章子节是否齐全（对照 outline.json）
        - 引用数量（Related Work ≥ 15, 全文 ≥ 25）
        - 公式数量（Methodology ≥ 5, 全文 ≥ 8）
        - 图表引用是否正确（Fig. 1, Table 1 等）
        - 实验数据是否来自 unified_results（非编造）
        - 创新点是否被所有锚定章节覆盖
        - Abstract 是否包含关键指标
        - Conclusion 是否总结所有创新点
        
        输出: completeness_score (0-100) + 详细清单
        """
    
    # ── L3: 学术质量 ──
    def eval_academic_quality(self, full_text: str,
                               venue_profile: Dict) -> Dict:
        """
        LLM 驱动的多维度评价（用评价模型 call_evaluation）:
        
        8个维度:
        1. 创新性表达 (novelty_expression): 创新点是否清晰、具体、有说服力
        2. 故事线推进 (narrative_progression): 每段是否在推进论点
        3. 方法论严谨 (methodological_rigor): 方法描述是否可复现
        4. 实验充分性 (experimental_sufficiency): 实验是否充分验证了创新点
        5. 引用质量 (citation_quality): 引用是否最相关、是否过时
        6. 写作风格 (writing_style): 是否符合目标 venue 风格
        7. 数据一致性 (data_consistency): 全文数字是否一致
        8. 格式规范 (format_compliance): 是否符合投稿格式要求
        
        输出:
        {
            "dimensions": {dim: score_0_100},
            "overall_score": ...,
            "strengths": [...],
            "weaknesses": [...],
            "comparison_with_venue": "above_average" | "average" | "below_average"
        }
        """
    
    def run_full_evaluation(self, output_dir: str, ...) -> Dict:
        """
        执行完整的三层评价
        
        输出:
        - output/evaluation_report.md  (人类可读报告)
        - output/evaluation_report.json (结构化数据)
        
        包含:
        - L1 格式有效性报告
        - L2 内容完整度报告（含覆盖率热力图）
        - L3 学术质量评价（8维度雷达图数据）
        - 总体评级 (A/B/C/D)
        - 改进建议（按优先级排序）
        """
```

---

### U8. Bug 修复

| Bug | 文件 | 修复方案 |
|-----|------|---------|
| dispatcher lambda 参数错误 | `agent/dispatcher.py` | lambda 签名从 `lambda:` 改为 `lambda task:` |
| Phase 6.5 auditor crash | `agent/auditor.py` | `audit_abstract()` 方法添加 None 检查 |
| P0 gate score=95 仍被阻断 | `agent/ordered_gate.py` | P0 通过阈值从 100 降为 90 |
| LaTeX 中残留 Markdown 语法 | `tools/latex_converter.py` | 增加清理步骤 |
| Ch4 内容重复 | `agent/loop.py` | Phase 7.26 去重增强 |

---

## 升级实施顺序（依赖拓扑）

```
批次1: 基础设施（无依赖）
  ├── U8  Bug 修复（5项）
  └── U5  PDF 编译管线（安装 pandoc + texlive）

批次2: 数据与引用（依赖批次1）
  ├── U1  实验数据单一数据源
  ├── U4  BibTeX 引用生成
  └── U7  输出有效性评价

批次3: 顶层设计（依赖批次2）
  ├── U2  创新点验证与递进设计
  └── U6  全局打磨阶段

批次4: 生成重构（依赖批次3）
  └── U3  段落级生成与质量控制

批次5: 集成测试
  └── 全流程 pipeline 运行 + 三层评价
```

---

## 测试验收标准（对标 IEEE TCSVT）

### 验收依据

对标 IEEE TCSVT 的 6 项有参考评价维度（来自 `reference_based_evaluation.json` 的真实 TCSVT 论文对比）：

| 维度 | TCSVT 真实论文标准 | v7.0 差距分 | v9.0 目标 |
|------|-------------------|:-----------:|:---------:|
| 创新点表述 | 窄而深，每个贡献有完整"问题-洞察-方案"链 | 7/10 | ≤ 4/10 |
| 章节结构深度 | 数学形式化定义 + 逐步推导 + 理论对比 + proof sketch | 8/10 | ≤ 5/10 |
| 实验表格/图表丰富度 | 5+ 数据集、8-12 SOTA 对比、5+ 消融、BadPix、计算效率 | 7/10 | ≤ 4/10 |
| 引用密度和准确性 | 50-70 篇，每篇有精准技术关联描述 | 8/10 | ≤ 4/10 |
| 公式严谨度 | 变量定义含维度、推导过程、凸性/可微性分析、符号表 | 8/10 | ≤ 5/10 |
| 总体差距 | 物理建模 + 方法深度 + 实验充分 + 写作深度 | 7/10 | ≤ 4/10 |

> 差距分越低越好。10 = 完全不达标，0 = 达到真实论文水平。

### L1: 格式有效性验收

| 检查项 | TCSVT 标准 | 验收阈值 |
|--------|-----------|---------|
| `.md` 全文文件 | 完整 Markdown | 存在 + > 15KB |
| `.tex` LaTeX 文件 | IEEEtran 模板, two-column | 存在 + `\documentclass[journal]{IEEEtran}` |
| `.tex` 编译 | 无致命错误 | `xelatex main.tex` 返回码 0 |
| `.pdf` 文件 | 12-14 页, two-column | 存在 + 页数 10-16 |
| `.bib` 参考文献库 | 50-70 条 BibTeX 条目 | 存在 + ≥ 25 条 |
| `.tex` 无 Markdown 残留 | 纯 LaTeX | `##`, `**`, `[N]` 出现 0 次 |
| `\cite{}` 引用 | numeric 风格 | `\cite{` 出现 ≥ 20 次 |
| IEEE 关键词 | `\begin{IEEEkeywords}` | 存在且非空 |
| IEEE 摘要 | `\begin{abstract}` | 存在 + 200-300 词 |

### L2: 内容完整度验收（TCSVT 章节预算对标）

| 检查项 | TCSVT Profile 标准 | 验收阈值 |
|--------|-------------------|---------|
| Introduction 篇幅 | 800 词 (600-1100) | 600-1200 词 |
| Related Work 篇幅 | 1000 词 (700-1500) | 700-1600 词 |
| Methodology 篇幅 | 2500 词 (1800-3500) | 1800-3600 词 |
| Experiments 篇幅 | 2000 词 (1500-2800) | 1500-3000 词 |
| Conclusion 篇幅 | 500 词 (350-700) | 350-750 词 |
| 5 个核心章节齐全 | Introduction/RW/Method/Exp/Concl | 全部存在 |
| Discussion 章节 | TCSVT extra_section | 存在且 ≥ 300 词 |
| 每章子节对照 outline | 与 outline.json 一致 | 覆盖率 ≥ 90% |
| 无 [TODO] / [PLACEHOLDER] | 0 个 | 0 个 |
| 引用总数 | TCSVT 50-70 篇 | ≥ 25 篇 (v9.0 先达到50%密度) |
| Related Work 引用密度 | 每子节 5-6 篇 | ≥ 3 篇/子节 |
| Methodology 公式数 | TCSVT ≥ 10 个编号公式 | ≥ 5 个公式 |
| 实验表格 | TCSVT 6-10 个 | ≥ 3 个表格 |
| 实验图表 | TCSVT 10-15 个 | ≥ 3 个图引用 |
| 消融实验 | TCSVT 4-7 组 | ≥ 3 组 |
| BadPix 指标 | TCSVT 光场标配 | 至少出现 1 次 |
| 数据集覆盖 | TCSVT 3+ 数据集 | ≥ 2 数据集 |
| SOTA 对比方法 | TCSVT 8-12 个 | ≥ 3 个 |
| 创新点被覆盖 | 每个创新点在 Method+Exp 中出现 | 100% 覆盖 |
| Abstract 含关键指标 | MAE/improvement 数据 | ≥ 2 个量化指标 |
| Conclusion 总结创新点 | 每个贡献点 1 句 | 覆盖所有创新点 |
| 数据一致性 | Abstract ↔ Exp ↔ Table 数值完全一致 | 0 处不一致 |

### L3: 学术质量验收（对标 TCSVT 审稿标准）

8 维度评价（用评价模型 `call_evaluation()` 执行）：

| 维度 | TCSVT 审稿标准 | v7.0 水平 | v9.0 及格线 | v9.0 目标 |
|------|---------------|:---------:|:----------:|:---------:|
| 1. 创新性表达 | 每个贡献有"问题-洞察-方案"完整链 | 35 | ≥ 60 | 70 |
| 2. 故事线推进 | 3 个创新点递进，每段推进论点 | 40 | ≥ 55 | 65 |
| 3. 方法论严谨 | 数学形式化 + 推导 + 理论对比 | 30 | ≥ 50 | 60 |
| 4. 实验充分性 | 5+ 数据集、8+ SOTA、5+ 消融、BadPix | 40 | ≥ 55 | 65 |
| 5. 引用质量 | 50+ 引用，每篇有精准技术关联描述 | 20 | ≥ 50 | 60 |
| 6. 写作风格 | formal/precise, video/systems-oriented | 55 | ≥ 60 | 70 |
| 7. 数据一致性 | 全文数字统一，Abstract ↔ 正文完全吻合 | 30 | ≥ 70 | 80 |
| 8. 格式规范 | IEEEtran two-column, numeric 引用, 符号表 | 45 | ≥ 65 | 75 |

**总体验收**:
- L1 全部 PASS（必要条件）
- L2 completeness_score ≥ 75/100
- L3 overall_score ≥ 60/100（及格线），目标 ≥ 65/100
- L3 任何单一维度不得低于 45/100

### TCSVT 审稿模拟验收

用 `call_evaluation()` 模拟 TCSVT 审稿流程：

```
审稿人1 (Methodology Expert):
  checklist:
  - 物理模型是否有从物理定律到方法设计的完整推导链？
  - 双掩码设计是否有明确的数学定义和适用边界？
  - "MRI启发"类比是否有数学等价性证明或被删除？
  - 方法论是否呈现"推导性"而非仅"描述性"？
  - 损失函数各项是否有物理意义解释？

审稿人2 (Experiment Expert):
  checklist:
  - 是否包含 BadPix(δ<0.03/0.07/0.1) 指标？
  - 消融实验是否覆盖每个核心模块独立贡献？
  - 是否有与直接竞争方法(如 ACO)的对比？
  - 是否有定性可视化(深度图/误差图/EPI线)？
  - 是否报告计算效率(参数量/FLOPs/推理时间)？

审稿人3 (Writing Quality Expert):
  checklist:
  - 引用是否 ≥ 50 篇且每篇有技术关联描述？
  - 符号系统是否全文统一且有符号表？
  - 章节过渡是否自然，叙事是否连贯？
  - Abstract 是否在 250 词以内且包含关键量化指标？
  - 是否符合 IEEE TCSVT two-column 格式规范？
```

**审稿结论标准**:
- 3 个审稿人均分 ≥ 65 → "Accept / Minor Revision"
- 3 个审稿人均分 ≥ 55 且无单一 < 45 → "Major Revision"
- 任何审稿人 < 45 → "Reject"

### 单元测试（每项完成后）

| 升级项 | 测试文件 | 测试数量 | 覆盖点 |
|--------|---------|:--------:|--------|
| U1 | `test/test_data_source.py` | 12 | 数据提取、占位符、一致性检查 |
| U2 | `test/test_innovation_verify.py` | 15 | 新颖性搜索、递进设计、锚定映射 |
| U3 | `test/test_paragraph_ctrl.py` | 18 | 段落规划、生成、检查、重生成 |
| U4 | `test/test_bibtex_builder.py` | 10 | key生成、[N]→\cite替换、.bib生成 |
| U5 | `test/test_pdf_compiler.py` | 8 | xelatex编译、pandoc编译、错误恢复 |
| U6 | `test/test_global_polish.py` | 10 | 过渡检查、术语统一、冗余消除 |
| U7 | `test/test_output_evaluator.py` | 15 | L1/L2/L3各层评价 |
| U8 | 修改现有测试 | 5 | bug修复验证 |

### 集成测试（全流程 Pipeline）

```bash
pipeline.py start --project /path/to/project --gpu 0

# TCSVT 验收清单
1. output/full_paper.md 存在且 > 15KB
2. output/latex/main.tex 存在且 \documentclass[journal]{IEEEtran}
3. output/latex/main.tex xelatex 编译通过 (返回码 0)
4. output/latex/references.bib 存在且 ≥ 25 条
5. output/full_paper.pdf 存在且 10-16 页
6. output/evaluation_report.json 存在
7. L1 全部 PASS
8. L2 completeness_score ≥ 75
9. L3 overall_score ≥ 60
10. L3 3个审稿人模拟均分 ≥ 55 (Major Revision 以上)
11. 数据一致性: 0 处不一致 (Abstract ↔ Exp ↔ Table)
12. 创新点覆盖率: 100% (每个创新点在 Method+Exp 出现)
```
```

---

## 预期效果（对标 IEEE TCSVT）

### 格式输出

| 指标 | v8.0 当前 | v9.0 目标 | TCSVT 标准 |
|------|:---------:|:---------:|:----------:|
| 输出格式 | .md + .tex | .md + .tex + .pdf | .tex + .pdf |
| LaTeX 模板 | IEEEtran | IEEEtran (编译通过) | IEEEtran two-column |
| BibTeX 引用 | 0 条 | ≥ 25 条 | 50-70 条 |
| PDF 页数 | 无 | 10-16 页 | 12-14 页 |

### 内容质量

| 指标 | v8.0 当前 | v9.0 目标 | TCSVT 标准 |
|------|:---------:|:---------:|:----------:|
| 创新点差距分 | 7/10 | ≤ 4/10 | 0/10 |
| 章节深度差距分 | 8/10 | ≤ 5/10 | 0/10 |
| 实验丰富度差距分 | 7/10 | ≤ 4/10 | 0/10 |
| 引用密度差距分 | 8/10 | ≤ 4/10 | 0/10 |
| 公式严谨度差距分 | 8/10 | ≤ 5/10 | 0/10 |
| 数据一致性 | 3处不一致 | 0处 | 0处 |
| L2 内容完整度 | 无评价 | ≥ 75/100 | 90+/100 |
| L3 学术质量 | ~55/100 | ≥ 60/100 | 75+/100 |

### 预估审稿结果

| 指标 | v7.0 | v8.0 | v9.0 目标 |
|------|:----:|:----:|:---------:|
| 审稿结论 | Reject | Major Revision | Major Revision → Minor Revision |
| 发表可能性 | 0% | 30-40% | 50-60% |

---

## 风险与降级

| 风险 | 影响 | 降级方案 |
|------|------|---------|
| texlive 安装失败（磁盘/权限） | 无 PDF | WeasyPrint 或纯 Python PDF |
| 创新点搜索无可信结果 | 延迟 Phase 0 | 降级为 LLM 自评估（降低权重） |
| 段落级生成增加 LLM 调用 | 成本+时间 | 关键章节段落级，其他章节保持原模式 |
| 全局打磨引入新问题 | 质量下降 | 打磨结果需经过 VERIFY 检查后才应用 |
