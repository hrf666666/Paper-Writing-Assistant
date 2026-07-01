# Paper Writing Assistant — 架构设计文档 v17.0

> **[English](architecture.en.md)** | 中文 | 版本: v17.0

本文档描述 v17.0 的**当前架构状态**。版本演进史见文末附录 A。

---

## 0. 分层治理架构（核心）

针对 PDF 实跑暴露的"审了不改、改了不验、改了不重审、重复审无仲裁"问题，v16.3 治理五批 + v17.0 G1/G4 补齐建立了政府治理比喻的六层架构。**改革的对象不是新增功能，是修复"审改验"流程的 12 个断点。**

### 0.1 六层架构

| 层 | 角色（比喻） | 模块 | 职责边界（纵向） | 横向边界 |
|----|------------|------|----------------|---------|
| **L1** | 省级政府 | `chapter_agent.py` ChapterAgent | 只管一章：生成→审→改→审计内聚；不碰别章 | 章=省，省间不串扰 |
| **L2** | 中央部委（纵向专项） | `vertical_checkers.py` 5个Checker | 只审不改：产 Finding 入 FindingBus | 每 Checker 一专项（bib/formula/table/figure/language） |
| **L3** | 中央政府（全文协调） | `output_evaluator.py` GlobalReviewer | 全文视野仲裁：章节 quality≥80 但全文 L3<70 时，全文说了算 | 全文 vs 章节，矛盾时全文决策 |
| **L4a** | 执行机构 | `fix_executor.py` FixExecutor | 只改不判：按 Finding 路由修复，确定性优先 | 改完交回，不评估对错 |
| **L4b** | 纪检 | `verifier.py` ContentVerifier | 只验不改：改完→复查→通过才 resolve | 独立于改方，防自评自验 |
| **L5** | 中央决策中枢 | `loop.py` + `quality_gate.py` 回归守卫 | 调度+最终把关：revise 后跑独立回归守卫 | 决策权最高，但不亲自审/改/验 |

**核心原则**（贯穿六层）：
1. **审改验分离**：审（L1/L2）→ 改（L4a）→ 验（L4b）→ 消解（FindingBus.resolve），三权不集中同一函数
2. **Finding 是唯一问题载体**：所有层通过 FindingBus 通信
3. **决策链单向清晰**：审→FindingBus→FixExecutor→Verifier复查→resolve
4. **省级自治 + 中央仲裁**

### 0.2 12 断点（已全部修复，代码逐行核验）

| 断点 | 定义 | 修复层 | 状态 |
|------|------|--------|------|
| B1 断链 | phase6_5 findings 录入后无消费 | L1 ChapterAgent 录入 FindingBus | ✅ |
| B2 幽灵修复 | L3 修订只重生成 tex 不重编译 PDF | L5 loop.py 重编译+重跑 Checker | ✅ |
| B3 自评自验 | quality_gate 审与验同一函数 | L5 回归守卫独立检查 | ✅ |
| B4 改完不重审 | 改完直接覆盖无复查 | L4a resolve + L4b Verifier 复查 | ✅ |
| B5 图无回路 | figure_review 只报不触发重画 | L2 FigureInspector + L4a 图缩节点 | ✅ |
| B6 公式空白 | 公式 0 审查 0 修改 0 验收 | L2 FormulaChecker + L4a 公式换行 | ✅ |
| B7 表内容无验 | 表格只验结构不验内容 | L2 TableChecker | ✅ |
| B8 无章节agent | 5 章走同一无差别流程 | L1 ChapterAgent 按章区分 | ✅ |
| C1 重复审查 | auditor 与 quality_gate 都审引用 | L1 ChapterAgent 内聚审计 | ✅ |
| C2 重复审查 | auditor 在 5.6/6.5 跑两遍 | L1 审计内聚 + phase6_5 轻量化 | ✅ |
| C3 无仲裁 | G4 结构分 vs L3 语义分矛盾无决断 | L3 GlobalReviewer 仲裁 | ✅ |
| C4 Finding不消解 | clear 按源清，critical 改后不降级 | FindingBus.resolve(finding_id) 按 ID | ✅ |

### 0.3 v17.0 G4 补齐：FactBase owner 三分类

旧 `_classify_owner` 二分类（非 baseline 即 ours）把"既非 ours 也非 baseline"的第三类数值（交叉验证/物理特征比/诊断分类）全塌缩进 ours，污染 `_compute_comparison` 配对。改三分类：**baseline / auxiliary / ours**。auxiliary 不进配对，但仍存 metrics 供查值。`as_fact_sheet` 渲染三栏。

同时补全字段抽取 key（hardware 在`训练策略.硬件限制`、datasets 在`组成与类型`、loss 叫`优化目标`、Epoch 单数）。

### 0.4 v17.0 G1 补齐：venue 驱动按章区分

chapter_elements 从硬编码改为 `venue_profile.content_patterns[章节名].chapter_elements` 驱动（零新增 profile 字段）。无数值章（`has_formula=False` 且非 Experiments）跳过 `_judge_metric_attribution` 的 LLM 调用。审计层 overclaim 守卫收窄（ch1 Introduction 跳过）。

---

## 1. 系统总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        pipeline.py (入口)                        │
│                          ↓ --no-resume                          │
│                    ResearchLoop.run()                            │
│              THINK → EXECUTE → VERIFY → REFLECT                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       ↓               ↓               ↓
  ┌─────────┐   ┌─────────────┐  ┌──────────┐
  │ Phase 0 │→→│ Phase 1~5   │→→│ Phase 6~9│
  │ 分析阶段│   │ 章节生成    │  │ 后处理   │
  │         │   │(ChapterAgent)│  │(治理闭环)│
  └─────────┘   └─────────────┘  └──────────┘
```

**核心设计原则**：
- LLM 直出 LaTeX（不走 Markdown 中间格式）
- 代码 = 裁判，LLM = 运动员
- 审改验分离（六层治理）
- 零信任验证：每一步都校验，不信任 LLM 输出
- 全链路降级：每个外部依赖都有 fallback

---

## 2. 目录结构

```
paper-writing-assistant/
├── pipeline.py                  # 主入口
├── run_with_log.py              # 日志 Tee 包装器
├── config/                      # 配置层
│   ├── project_config.py        # 项目配置
│   ├── api_config.py            # API + Provider 配置
│   └── venue_profiles/          # 11 个期刊/会议配置
├── api/                         # API 客户端层
│   ├── openai_compatible.py     # 统一 OpenAI 兼容客户端
│   ├── mcp_http_client.py       # MCP StreamableHTTP 客户端
│   ├── web_search_api.py        # 智谱 Web Search API
│   └── paper_search.py          # 论文检索降级链
├── agent/                       # Agent 核心层
│   ├── core/                    # 内核契约层（5 块，零循环依赖）
│   │   ├── errors.py            #   错误分级 + classify()
│   │   ├── factbase.py          #   FactBase 单一事实源（owner 三分类）
│   │   ├── finding.py           #   Finding 统一问题 + FindingBus
│   │   ├── figure_manifest.py   #   FigureManifest 文图联动
│   │   └── citation_base.py     #   CitationBase 引用契约
│   ├── loop.py                  # 自主循环引擎（系统心脏）
│   ├── chapter_agent.py         #   🔄 L1 省级章节 agent（venue 驱动）
│   ├── auditor.py               #   反幻觉审计（L1 审计内聚）
│   ├── quality_gate.py          #   质量门控 + L5 回归守卫
│   ├── verifier.py              #   🔄 L4b 纪检验收
│   ├── fix_executor.py          #   🔄 L4a 执行机构
│   ├── cross_chapter_checker.py #   跨章节一致性（读 FactBase）
│   ├── venue_adapter.py         #   期刊适配器
│   ├── hierarchical_planner.py  #   分层任务规划
│   ├── api_client.py            #   统一 API 客户端
│   ├── skill_orchestrators/     #   章节编排器
│   └── checkpoint.py            #   断点恢复
├── tools/                       # 工具层
│   ├── vertical_checkers.py     #   🔄 L2 纵向 Checker（5 专项）
│   ├── output_evaluator.py      #   🔄 L3 评价 + GlobalReviewer 仲裁
│   ├── latex_converter.py       #   LaTeX 组装
│   ├── bibtex_builder.py        #   BibTeX 生成
│   ├── arch_diagram_renderer.py #   架构图渲染
│   ├── figure_generator.py      #   TikZ 图表生成
│   ├── pdf_compiler.py          #   XeLaTeX 编译
│   └── pdf_validator.py         #   PDF 验证
├── figure/
│   └── style_templates.py       #   期刊风格模板（唯一活依赖）
├── skills/academic_writing_style/
│   ├── writing_discipline.md    # P0 跨期刊通用写作纪律
│   └── style_guide.md           # P3 IEEE 特有写作规范
├── test/                        # pytest 测试（92；test_unit/ 另 449，均 gitignore）
└── data/reference_packs/        # 离线论文数据包
```

---

## 3. 核心循环：THINK → EXECUTE → VERIFY → REFLECT

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  THINK   │────→│ EXECUTE  │────→│  VERIFY  │────→│ REFLECT  │
│ 规划任务 │     │ 执行任务 │     │ 纯代码验证│     │ LLM评估  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
      ↑                                                  │
      └──────────── 质量不达标则重试 ─────────────────────┘
```

| 阶段 | 职责 | LLM 参与 |
|------|------|---------|
| THINK | 分析当前状态，规划下一步任务 | 否（规则引擎） |
| EXECUTE | 调度器分发任务给 Worker | 是（章节生成等） |
| VERIFY | 纯代码检查（引用/数据/公式/去重/标记/结构/符号） | 否 |
| REFLECT | LLM 评估结果质量，更新记忆，决定下一步 | 是 |

---

## 4. Phase 流水线

### 4.1 Phase 0 — 分析阶段

| Phase | 名称 | 模块 | 功能 |
|-------|------|------|------|
| 0.1 | 工程代码分析 | `project_analyzer.py` | 扫描 PROJECT_CODE_PATH，提炼创新点/模型架构/实验设计 |
| 0.2 | 参考论文分析 | `ref_pdf_analyzer.py` | 加载 ref_md/（Markdown 优先）或 ref_pdf/（PDF），提取风格/组织 |
| 0.3 | 创新点验证 | `innovation_verifier.py` | 新颖性验证 + 递进设计 |
| 0.5 | 参考池+大纲 | `structure_planner.py` | 离线包+OpenAlex → reference_pool（51+ 篇）+ outline.json |
| 0.6 | 动机确认 | `motivation_engine.py` | 强制确认论文动机（开关 ENABLE_MOTIVATION_ENGINE） |
| 0.65 | 风格+策略 | `content_strategist.py` | 期刊风格学习 + 内容策略规划 |
| 0.7 | ~~范例学习~~ | — | ⚠️ v14 已删（exemplar_learner 空转占位） |
| 0.8 | 引用支撑库 | `citation_injector.py` | claims → 注入章节 prompt |
| 0.9 | ~~理由矩阵~~ | — | ⚠️ v14 已删（rationale_matrix 空转占位） |
| 0.95 | 消融实验 | `ablation_designer.py` | 消融实验自动化（开关 RUN_ABLATION） |
| 0.98 | FactBase | `loop._build_paper_context` | 构建单一事实源，owner 三分类，持久化 factbase.json |
| 0.99 | 图预规划 | `loop._plan_figures_early` | 章节前文图联动规划 |

### 4.2 Phase 1~5 — 章节生成（🔄 走 ChapterAgent）

| Phase | 章节 | 说明 |
|-------|------|------|
| 1 | Introduction | ChapterAgent.run(1)：生成→质量闭环→子节校验→审计内聚 |
| 2 | Related Work | ChapterAgent.run(2) |
| 3 | Methodology | ChapterAgent.run(3)（has_formula=True，触发 numeric judge） |
| 4 | Experiments | ChapterAgent.run(4)（has_table=True） |
| 5 | Conclusion | ChapterAgent.run(5) |

**每章 ChapterAgent.run 全流程**：生成 → `_quality_ensure` 质量闭环（最多 3 轮）→ `_verify_with_awareness` 子节校验（venue 驱动短路）→ `_audit_chapter` 审计内聚 → FindingBus 录入 → 存储。

**扩展章**：5.1 Discussion / 5.2 Limitations（venue 配了才生成）/ 5.5 摘要+关键词 / 5.6 前移审计。

### 4.3 Phase 6~9 — 后处理（治理闭环）

| Phase | 名称 | 治理层 | 功能 |
|-------|------|--------|------|
| 6 | 参考文献审查 | — | 验证引用可检索性 |
| 6.5 | cross_chapter 协调 | L1 横向 | ⚠️ 已轻量化（审计已内聚 ChapterAgent），只跑跨章一致性 |
| 7.x | 输出组装 | — | 全局打磨→图表生成→LaTeX→BibTeX→约束预检 |
| **8** | **编译+前置审查** | **L2+L4a+L4b** | run_all_vertical_checks → execute_fixes → Verifier 复查 → PDF 编译 |
| **8.5** | **PDF 验证** | — | 结构+视觉验证（max 3 轮修复） |
| **8.8** | **分层验收** | — | 原子级/抽象级/全局级验收 |
| **9** | **评价+闭环** | **L3+L5** | L3 对抗式审稿 → issues 录入 → 闭环重写 → 重编译（B2 幽灵修复） |

### 4.4 治理六层 → Phase 映射

| 治理层 | 跑在哪个 Phase | 代码调用点 |
|--------|---------------|-----------|
| L1 ChapterAgent | Phase 1-5 章节内 | `loop.py chapter_agent.run(ch_num)` |
| L2 纵向 Checker | Phase 8 前置 + Phase 9 闭环后 | `loop.py run_all_vertical_checks` |
| L3 GlobalReviewer | Phase 9 | `loop.py run_output_evaluator` |
| L4a FixExecutor | Phase 8 + Phase 9 闭环后 | `loop.py execute_fixes` |
| L4b Verifier | Phase 8（复查才 resolve） | `loop.py` Verifier 复查 |
| L5 回归守卫 | Phase 1-5 revise 后 + Phase 9 重编译 | `quality_gate.py _check_revise_regression` |

---

## 5. 核心模块设计

### 5.1 API 客户端（降级链）

```
调用请求
   │
   ↓
┌──────────────────────────────────────────────┐
│          api_client.py (UnifiedAPIClient)     │
│  GENERATION_MODELS 降级链（v15.3 后仅 GLM）：   │
│  glm-5.2 → glm-5.1 → glm-4.7 →              │
│  glm-5 → glm-4.5v → glm-4.6v                │
│  每个 Provider 最多重试 2 次，全失败抛 AllModelsExhausted │
└──────────────────────────────────────────────┘
```

**三级模型分层**：生成（glm-5.2/5.1 `call_generation`）/ 推理（glm-5.2/5.1/4.7 `call_reasoning`）/ 轻量（glm-4.6v/5/4.5v `call_light`）。

**评价模型隔离**：评价模型优先与执行模型来自不同 Provider（避免"自我审查"盲区），由 `resolve_eval_models()` 动态解析。

### 5.2 LLM 调用基类

`base_orchestrator.py`：call_generation / call_reasoning / call_light / call_evaluation / parse_json_with_retry / save_output。

### 5.3 LaTeX 组装

Chapter Prompt（原生 LaTeX）→ `_minimal_cleanup`（清理 [?]、空 section、Markdown 残余）→ Phase 7.x（全局打磨→图表→组装）→ `output/latex/main.tex` → Phase 8（XeLaTeX 编译）→ `output/full_paper.pdf`。

### 5.4 引用处理流水线

```
Phase 0.5a: 离线数据包 + OpenAlex → reference_pool.json (51+ 篇)
Phase 0.8:  build_citation_bank() → claims
Phase 1-5:  LLM → <citation> 标记
Phase 7.8:  [N] → \cite{key} + BibTeX（CitationBase.build_bib 单一入口）
Phase 8:    XeLaTeX 编译 → PDF
```

**v17.0 cite 守恒守卫**：cite key 全程守恒，单一真相源 inject，引用 100% 可追溯。

### 5.5 FactBase 单一事实源

FactBase 是数值/事实的**单一真相源**（`agent/core/factbase.py`）。旧版 PaperContext 存在 auditor/verifier 各自从 project_data 重推导导致数值分歧，v13 起统一收敛到 FactBase。

```
Phase 0.98: loop._build_paper_context()
       ↓ 从 project_data + experiment_design 提取（G4-b 补全真实 key 别名）
FactBase = { hardware, training_params, loss_terms, datasets, metrics, model_name }
       ├─→ 持久化 output/factbase.json
       ├─→ G4-a: owner 三分类（ours / baseline / auxiliary），auxiliary 不进配对
       └─→ 注入 cross_chapter_checker / citation_injector / auditor
```

### 5.6 风格系统层级

P0 writing_discipline.md（跨期刊通用 10 条）→ P1 venue_profile（内容编排 + chapter_elements）→ P2 ieee_trans_style_profile.py（IEEE 硬规则）→ P3 style_guide.md（IEEE 特有规范）。

### 5.7 评价体系（L1/L2/L3）

```
Grade = L1 × 0.10 + L2 × 0.35 + L3 × 0.55
A ≥ 80, B ≥ 65, C ≥ 50, D < 50

L1 格式有效性（12 项）：IEEE模板/无Markdown/无占位符/cite有效/...
L2 内容完整度（6 项）：章节/字数/cite≥25/公式/表格≥3/无占位符
L3 学术质量：paperjury 对抗式审稿（Fatal-flaw + Forensic 两轮）

强制 D：critical_fails 存在 或 L1 < 60
GlobalReviewer 仲裁（L3）：章节 quality≥80 但全文 L3<70 时，全文级有最终决策权
```

---

## 6. 降级链设计

- **6.1 API**：`glm-5.2 → glm-5.1 → glm-4.7 → glm-5 → glm-4.5v → glm-4.6v`
- **6.2 学术搜索**：`离线数据包(32篇) → MCP 智谱 Web Search → OpenAlex(300M+)`（境内 S2/CrossRef/DBLP 超时，SKIP_ONLINE_VERIFICATION=1）
- **6.3 BibTeX**：metadata 模板直接生成（100% 成功，<1s/条）
- **6.4 参考论文**：`ref_md/*.md（优先）→ ref_pdf/*.pdf（PDF 解析）`

---

## 7. 关键设计决策

- **7.1 LLM 直出 LaTeX**：不走 Markdown→LaTeX 中间转换
- **7.2 代码=裁判，LLM=运动员**：所有 LLM 输出都经纯代码校验
- **7.3 章节统一分发**：Phase 1-5 统一通过 `chapter_agent.run(ch_num)`（venue 驱动）
- **7.4 上下文管理**：无独立 bounded_context 模块；FactBase 持久化 + citation_context 内联指纹缓存 + previous_summary 拼接

---

## 8. 配置体系

### 8.1 期刊 Profile 系统（11 个）

6 期刊（IEEE TCSVT/TIP/TPAMI/IJCV/Pattern Recognition/Displays）+ 5 会议（CVPR/ICCV/ECCV/AAAI/NeurIPS）。未命中降级到 IEEE TIP。每个 Profile 定义阈值/篇幅/内容编排模式/`chapter_elements`。

> **⚠️ 技术债**：当前 Profile 用 Python class（~1650 行），本质是指引+约束，应迁移为 Markdown。

### 8.2 关键阈值（base_profile 默认）

| 参数 | 值 | 用途 |
|------|---|------|
| `quality_pass_threshold` | 70.0 | 质量门控通过阈值 |
| `quality_max_retries` | 3 | 章节最大修订轮次 |
| `min_references` | 25 | L2 引用最低数量 |

---

## 9. 数据流图

```
PROJECT_CODE_PATH/          ref_md/ + ref_pdf/
         │                          │
         ↓                          ↓
   Phase 0.1 代码扫描         Phase 0.2 参考论文分析
         │                          │
         └──────────┬───────────────┘
                    ↓
         Phase 0.5~0.99（规划 + FactBase + 图预规划）
                    ↓
         Phase 1-5（ChapterAgent 章节生成）
                    ↓
         Phase 7（输出组装）+ Phase 8（编译）
                    ↓
       main.tex    references.bib   full_paper.pdf
                    ↓
         Phase 9（L1/L2/L3 评价 + L3 闭环重写）
                    ↓
          evaluation_report.json
```

---

## 10. 运维

### 启动

```bash
python pipeline.py              # 自动从断点恢复（默认）
python pipeline.py --no-resume  # 从头开始
python pipeline.py --debug      # 调试模式
python pipeline.py --title "My Paper Title"        # 覆盖标题
python pipeline.py --output ./my_output            # 覆盖输出目录
python pipeline.py --code-path /path/to/project    # 覆盖代码路径
```

### 断点恢复

检查点存 `output/.checkpoints/`（index.json + state/ 每 key 独立文件）。每个 phase 完成后自动保存；异常/中断时存 failed/interrupted 状态。

### 输出

```
output/
├── full_paper.pdf              # 最终 PDF
├── latex/main.tex              # LaTeX 源码
├── latex/references.bib        # BibTeX
├── factbase.json               # FactBase 事实库
├── experiment_design.json      # 实验设计
├── figure_plan.json            # 图表规划
├── reference_pool.json         # 参考文献池
├── chapter1~5/                 # 各章中间文件
├── evaluation_report.json      # 评价结果
└── .checkpoints/               # 断点恢复
```

---

## 11. PaperJury 统一评价范式

一个评价范式（paperjury），两个时机（生成时+终局），一个修订闭环（QualityGate）。生成阶段 QualityGate evaluate 用 paperjury 两轮审稿（issues + evidence_anchor + close_criterion）。终局 Phase 9 用同一范式全文审稿。L3 major issues 触发段落级带真相重写闭环（`_run_l3_revision_loop`），重写后重编译 PDF（B2 幽灵修复）。

---

## 附录 A：架构演进史

| 版本 | 关键变更 |
|------|---------|
| **v17.0** | 分层治理六层闭环 + FactBase owner 三分类 + venue 驱动按章区分 + 死代码清理 + 双语文档 |
| v16.3 | 引用子系统治本（cite 守恒守卫）+ 数值校验正则降级 + resume 状态同步 + 治理五批（12 断点修复） |
| v16.2 | 边写边改 + 全文检查闭环（线性→闭环） |
| v16.1 | 带真相的段落级重写 `_revise_with_evidence`（第三道防线） |
| v16 | 数值可信三道防线（真相注入+写后检测+重写） |
| v15.9 | FixAction executor + warning 可见化 |
| v15.8 | 弱点一致性闭环 + FactBase 对比结论 |
| v15.7 | 文图联动治本（规划前移 + 通信回路） |
| v15.6 | 实跑后深挖根因修复（4 bugfix） |
| v15.5 | 引用前置校验门 + figure plan 固化 |
| v15.3 | 评价可信化 + 数值 owner 真相源 + 前移闭环 |
| v14 | 内核契约层（errors/FactBase/Finding/FigureManifest/CitationBase）+ paperjury |
| v13 | 内核重建 + 接线消死接线 + Wave 1-6 瘦身 |
| v12 | 架构修正（通用性/特性分离）+ 引用管线修复 + PipelineContext |
| v11 | 境内自适应 + 参考文献系统重构（离线包为主） |
| v10.1 | 期刊自适应 + 内容策略驱动 |
| v9.0 | 首次完整论文输出（LaTeX 直出 + 溢出自愈） |
