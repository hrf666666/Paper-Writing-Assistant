# Paper Writing Assistant — 架构设计文档

> 版本: v16.3 | 更新: 2026-06-29

---

## 0. v16.3 引用子系统治本 + 数值校验正则降级 + resume 状态同步

> **v16.3 修掉既有防线的"假通过"——全量 pipeline 暴露的 3 类真实矛盾，逐个治本。
> 验证标准是全量 pipeline（phase0→9），不是单阶段 resume（后者会掩盖矛盾）。**

### 0.1 引用子系统治本——cite 守恒守卫 + 单一真相源 inject

> **根因**：LLM 编译修复（3 条路径）会把占位符 `<cite/>` 改写成裸 `\cite{author}`，
> 旧 cite 守卫只数数量、正则匹配不到真实占位符，形同虚设。

> - **cite 守恒守卫**（`_cite_keys_conserved`，tools/latex_converter.py）：
>   复用 CitationBase 唯一提取器，判 key 集合守恒（允许新增、禁止删减/改写）。
>   覆盖 3 处守卫：`_safe_llm_replace`（phase7/8 编译修复）、`_fix_chapter_latex`
>   （逐章 dry-compile）、`pdf_validator._is_valid_latex_response`（phase8.5）。
>   占位符集合必须相等 + cite key 集合 candidate⊇original。
> - **inject 单一真相源**：phase7.8 inject 是唯一 key 解析点，CitationBase 是唯一真相源。
>   裸名 key 7+ → 0。
> - **bib 时序修复**：inject 前移到 bib 构建之前，bib 用 `CitationBase.build_bib(tex)`
>   基于 inject 后实际 cite key 构建（旧逻辑读空 map → bib 1字节）。bib 0→25 条，完全匹配。
> - **代码块清理**（`_lint_latex`）：LLM 脏输出 ```代码块——含裸 cite 整块删，干净内容剥标记保留。

### 0.2 数值校验正则降级——LLM+FactBase 真相判断 + 改完重评闭环

> **根因**：phase5_6 用「正则扫数值 + ±60字符窗口 + metric 词表」判断数值归属——这是
> 语义任务，正则原理上做不对。把正确的"mixed urban scenes (MAE 0.119)"判成张冠李戴
> → `_revise_paragraphs` 盲改直落盘（旁路 quality_gate 闭环）→ 30次震荡 → 段落变乱码。
> 而验收"100%通过"没发现（只查结构不查内容）。**

> **深层矛盾**：能做语义判断的（LLM）和数值真相（FactBase）被割裂——
> quality_gate 懂语义但看不到真相，正则检测器有真相但不懂语义。
> 两个各只有一半能力，正则这一半反而抢了话语权（能直接改写、旁路闭环）。

> **治本（拼合被割裂的能力）**：
> - 正则**只干定位**（找 FactBase 数值 + 截取上下文段落，可靠），**删掉判归属**。
> - 新增 `_judge_metric_attribution`（agent/loop.py）：把（含数值段落 + FactBase 真相）
>   喂给 LLM 做语义判断，返回 all_correct/has_errors + evidence。
> - 新增 `_revise_with_evidence`：带 evidence 的精确修订（替代盲改）。
> - phase5_6 改为**改完重评闭环**：all_correct 就停（正确内容不动，震荡消除），
>   has_errors 才修订，修订后重评，受 `MAX_NUMERIC_FIX_ROUNDS=3` 上限保护。
> - `_verify_subsection` numeric 降级为定位标记；cite/figure 部分（用 CitationBase/manifest）不动。

> **实证**（真实 API + 真实 FactBase）：GOOD(0.119正确)→all_correct不误改；
> BAD(0.2953张冠李戴)→has_errors精准抓出；GARBAGE(乱码)→has_errors识别损坏。
> 9单测+53回归全过。

### 0.3 resume 状态同步修复

> - `_ensure_resume_state`：从 ctx 回填 self._reference_pool/_citation_bank/_factbase
>   + 从磁盘 factbase.json 重建 FactBase + 触发 CitationBase 构建（旧逻辑全 None→inject短路）。
> - **路径A 章节磁盘优先重载**：旧检查点章节含裸 cite 时，从磁盘 chapter*.md（占位符契约）覆盖。
> - **归档 bug 修复**：`_setup_output_dir` 检测到检查点时跳过归档（resume 复用），仅首次跑归档。
> - **G3/G4 验收修复**：`figure_plan_exists` metric 注册 + `_read_chapter_words` 剔除 LaTeX 标记
>   + Conclusion 阈值 500→350。

---

## 0.5 分层治理架构（v16.3 治理五批 + G1/G4 补齐）

> **本节固化六层治理架构 + 12 断点 + 审改验分离原则。
> 这些定义原本只在治理五批 commit message + 历史对话里，现固化为权威文档。**

### 0.5.1 六层架构（政府治理比喻）

针对 PDF 实跑暴露的"审了不改、改了不验、改了不重审、重复审无仲裁"问题，建立六层治理架构。
**改革的对象不是新增功能，是修复"审改验"流程的 12 个断点。**

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
4. **省级自治 + 中央仲裁**：省级处理章内事务，矛盾上交中央

### 0.5.2 12 断点（已全部修复，代码逐行核验）

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

### 0.5.3 G4 补齐：FactBase owner 三分类 + 字段抽取

> **修复治理架构地基的真 bug：数值防线建立在错误的 owner 分类上。**

**G4-a owner 三分类**（`factbase._classify_owner`）：
- 旧二分类（非 baseline 即 ours）把"既非 ours 也非 baseline"的第三类数值（交叉验证/物理特征比/Phase1 诊断分类）全塌缩进 ours，污染 `_compute_comparison` 配对。
- 改三分类：baseline / **auxiliary**（新增）/ ours。auxiliary 不进 ours vs baseline 配对，但仍存 metrics 供查值。
- `as_fact_sheet` 渲染三栏：ours 权威值 / baselines 对比值 / auxiliary 辅助值。
- 真实数据验证（output_6_23 factbase）：8 baseline + 6 auxiliary（旧代码这 6 条全误判 ours）。

**G4-b 字段抽取 key 补全**（`loop._build_paper_context`）：
- 真实 experiment_design.json 的 key 与抽取逻辑系统性不匹配（hardware 在`训练策略.硬件限制`、datasets 在`组成与类型`、loss 叫`优化目标`、Epoch 单数 / Batch size 带空格）。
- 补全 key 别名 + 嵌套层兜底 + 空 list 误判修复。真实数据验证：hardware/datasets/loss 在 2/3 个真实样本能抽到值。

### 0.5.4 G1 补齐：venue_profile 驱动按章区分 + 校验/审计短路

> **接通 ChapterAgent 按章 awareness，做"无内容章的前置短路"。**

**venue 驱动**（复用 `content_patterns` dict，零新增 profile 字段）：
- chapter_elements 配置从 `_CHAPTER_ELEMENTS` 硬编码改为 `venue_profile.content_patterns[章节名].chapter_elements` 驱动。
- ChapterAgent `_get_elements` 优先读 venue，未配则 fallback `_CHAPTER_ELEMENTS`。

**接通短路**：
- 校验层：无数值章（`has_formula=False` 且非 Experiments）跳过 `_judge_metric_attribution` 的 LLM 调用，节省 ch1/ch2/ch5 成本。
- 审计层：`_check_method_overclaim` 守卫从 Methodology/Introduction/Abstract 收窄为 Methodology/Abstract（ch1 Introduction 无方法正文，跳过）。

---

## 1. v16.2 边写边改 + 全文检查闭环（架构升级）

> **v16.2 统一了 v15.5-v16.1 的碎片防线——pipeline 从线性（生成→检测→报告）变成闭环
> （边写边改+全文检查闭环）。** 所有问题的共同根：论文声称 vs 真相源不一致。
>
> - **模块A 统一真相上下文**（`truth_context`）：合并 architecture/experiment 真相 +
>   自动矛盾标注（零参数+SAM→标注），经 planning_block 注入所有章节。token≤9KB。
> - **模块B 子节即时校验**（`_verify_chapter_subsections`）：整章按\n\n切分子节，逐个
>   确定性正则校验（cite/数值/图），有错带真相重写。零 LLM 调用（只检测到错才调）。
> - **模块C L3 闭环重写**（`_run_l3_revision_loop`）：L3 major→evidence_anchor 定位段落
>   →带真相重写→重新生成 main.tex。L3 从终局评价变成闭环检测器。
> - **核心设计**：确定性的事让代码做（正则校验），语义的事让 LLM 做（L3 理解+真相重写），
>   不靠正则提取语义声称（不完备），不靠字符串替换（蠢）。

## 1. v16.1 带真相的段落级重写（第三道防线）

> **v16 建了前两道防线，但检测到的错误修正不了。v16.1 补第三道防线。**
> - `_revise_paragraphs`：检测到数值张冠李戴→定位段落→FactBase 真相+错误拼给 LLM→重写这段。
> - 三道防线完整：真相注入(防线1)→写后检测(防线2)→带真相段落重写(防线3)。

## 2. v16 数值可信——"可用参考稿"缺失的核心一环

> cite 有两道防线，数值没有。v16 给数值加同样的两道防线。
> - 防线1（`_compute_pairing_constraint`）：FactBase 配对约束注入 prompt。
> - 防线2（`_validate_metric_attribution`）：编译前扫描数值归属，检测张冠李戴。

## 3. v15.9 FixAction executor + warning 可见化

> 系统性问题：warning 死信（FindingBus 的 warning 从不被消费）。
> - FixAction executor：Phase 5.6 后自动执行 auto_apply replace_number。
> - findings_report.json：落盘所有 warning+ findings。

## 4. v15.8 弱点一致性闭环 + FactBase 对比结论

> E3+L3 统一诊断：叙事分裂（abstract 声称优越但 Limitations 承认退步）。
> - FactBase 对比结论（`_compute_comparison`）：预计算胜负，Overall 退步时警告。
> - abstract 注入 Limitations + FactBase。cross_chapter 跨章节一致性检查。

## 5. v15.7 文图联动治本（规划前移 + 通信回路）

> **v15.7 解决地基级问题——文图联动通信断裂**。v14 FigureManifest 承诺"文图联动单一真相源"，
> 但 figure_planner 在 Phase7.28（章节后）规划，结果从未流入章节生成 → 7 张图全 orphan。
>
> **问题本质 = 通信断裂**（planner 规划了图，但结果不流入章节），非归属之争。经三圈推理排除：
> - ❌ 粗+精二次规划（臃肿：3 层机制解 1 个通信问题）
> - ❌ 图归章节（致命：全局协调丧失）
> - ❌ prompt 硬编码（打补丁：动态规划对不上硬编码 ref）
>
> **解法（4 处改动 ~60 行）**：
> - **phase0_99 规划前移**（`loop._plan_figures_early`）：章节前用 abstract+innovation 规划
>   （method_text 空），写 figure_plan.json + 填 manifest(PLANNED) + 构建 figure_directives。
>   关键验证：所有图的信息需求在章节前就绪（teaser 需 abstract 非 method）。
> - **通信回路**（`_chapter_common.planning_block`）：读 figure_directives 按 _TYPE_TO_SECTION
>   拼引用指令，注入章节 prompt。复用 v14 planning_block 范式，**零章节签名/prompt 改动**。
> - **Phase7.28 复用**：ablation_hash 一致 → 读前移 plan 不重新规划；add→update 防 duplicate；
>   渲染前用成品 method 补粗糙 caption。
>
> **数据流**：phase0_99 规划→manifest(PLANNED)+directives → phase1-5 planning_block 注入
> → 正文 \ref{fig:xxx} → phase7.28 渲染+update(RENDERED) → phase7.3 注入 LaTeX

## 1. v15.6 实跑后深挖根因修复（4 个 bugfix）

> **v15.6 来自 v15.5 实跑的综合分析 + 根因深挖**。逐个错误挖到代码行级，并反思
> "为何历史 review 漏检"。4 项修复（~80 行），无架构改动。
>
> - **E1 图墙时序错位**（`loop.py` Phase 7.3）：
>   - v15.4 #3 的盲区：注入锚点只认 `\bibliographystyle`，但 Phase 7.3 执行时刻
>     tex 里是 `\begin{thebibliography}`（要等 Phase 7.8 才转换）→ 走 elif 把图
>     插在 thebibliography 之后 → 7 张 figure* 全堆在参考文献后（图墙）。
>   - **review 漏检根因**：逻辑正确 ≠ 时序正确。v15.4 review 只验证代码逻辑，
>     没问"Phase 7.3 执行时 tex 里到底有没有 bibliographystyle"。
>   - 修复：锚点列表 `[bibliographystyle, thebibliography, bibliography{]` 优先级匹配，
>     图必插在参考文献区之前；位置校验扩展到 bibliography 锚点。
>
> - **E2 None 污染**（`citation_injector.py:148` + `text_utils.py`）：
>   - 双 bug 叠加：`str(p.get("year"))` 当 year=None → "None" 字符串污染；
>     surname `name.split()[-1]` 取末位作者（He）而非首作者（Wang）。
>     结果：heNone 畸形 key 进真相源。
>   - **review 漏检根因**：默认值兜不住 None。`.get("year","")` 看似安全，
>     但只防缺键不防 None 值；测试从没构造 year=None case。
>   - 修复：year 显式类型判断（int/数字字符串才接受）+ surname 取首作者姓。
>
> - **E4 overclaim 反向校验**（`auditor._check_method_overclaim`）：
>   - auditor 原只查"应提未提"（正向遗漏），不查"凭空包装"（负向 overclaim）。
>     LLM 把 L2损失+Sigmoid 冒充成"基于 Maxwell 波矢力学"。
>   - 修复：新增反向校验，抓"基于/grounded in X理论"表述，对照真实代码
>     （loss_config_content/model_content）+ innovation_names；抓 overclaim，
>     放过代码里真实存在的术语（sigmoid/L2）。
>
> - **E5 validator 矢量图识别**（`pdf_validator.py`）：
>   - 空白页判定只数文字面积，TikZ/pgfplots 矢量图（get_images 检不到）→ 图墙页
>     判空白（假阳性 [10,11,12,13]）。**review 漏检根因**：测试覆盖常见路径，
>     没覆盖"图密集型论文"边界。
>   - 修复：用 get_drawings() 识别矢量图，有图页不算空白；valid 判定不再被
>     text_coverage 阈值（旧 0.3，图论文达不到）误杀。
>
> - **推迟 v15.7**：E3 数值矛盾（Lambertian MAE Intro 0.411 vs Conclusion 0.081）
>   需 FactBase 加实验条件溯源字段，属架构改动，不混进 bugfix 小版本。

## 1. v15.5 引用前置校验门 + figure plan 固化

> **v15.5 治愈两个系统性问题**（基于 6/22 vs 6/23 对照实测）。根因：cite key 仅靠
> prompt 祈使句约束 + Phase 7.8b 事后静默删（损伤正文）；figure plan 每次 LLM 现规划
> 不落盘（回落 3 张 default 导致缺图）。2 项改动，无新模块：
>
> - **A1 引用前置校验门**（`loop._validate_cite_keys`）：Phase 7.8 写盘后先于 7.8b 跑。
>   真相源 = `_cite_key_map`（CitationInjector 用 `generate_bib_key` 确定性生成）。
>   - 合法 key 通过；同 surname+年份差≤1 的笔误 fuzzy 修正（如 he2015→he2016）；
>   - 编造 key（如 `urbanlf_dataset`，无年份形态）→ 替换为 `\textbf{[REF?-原key]}` 留痕，
>     **不再静默删**（保留可见性供人工/末轮处理）。
>   - Phase 7.8b 的"正则删 cite"分支删除（编造 key 已被前置门拦截）。
> - **A2 figure plan 固化**（`loop._generate_figures` + `figure_planner.plan_figures`）：
>   - plan 结果落盘 `figure_plan.json`（带 `_source`/`_planned_at`/`_ablation_hash`）；
>   - 后续读盘复用，ablation hash 不一致才重新规划——checkpoint resume 不再缺图；
>   - `_default_plan` 3→4 张（+module_detail 方法图）；plan 来源（llm/fallback/default_4）可观测。
> - **推迟 v15.6**：L3 离散计数稳定性 + G4 Conclusion 字数闭环（需动评价范式）。

## 1. v15.3 评价可信化 + 数值 owner 真相源 + 前移闭环

> **v15.3 治愈 v14 评价模块的诊断→改进断裂。** 根因：`as_fact_sheet` 一行代码把
> baseline 数值标成 "Ours 权威值"（3 环节连环放大），导致 LLM 误用 baseline 值 +
> cross_chapter 查"存在性"非"语义" + FindingBus 后半程无消费者。4 层 11 项改动：

| 层 | 改动 | 文件 |
|----|------|------|
| L0 评价可信化 | L1/L2 去重 + 阈值按字数缩放 + conclusion 定位用 `\section` | output_evaluator.py |
| L1 owner 真相源 | as_fact_sheet 分组渲染 + training_params 进库 + cross_chapter owner 对账 | factbase.py, cross_chapter_checker.py, loop.py |
| L2 前移闭环 | Phase 5.6 草稿态审计（auditor+cc）→ critical 触发 rerun | loop.py, hierarchical_planner.py |
| L3 末轮机械 | 引用真实性 + 图-ref 一致 + undefined ref warning | output_evaluator.py |

**关键设计决策：**
- owner 修 + 前移是 AND 关系（owner 修让 cross_chapter 抓得到，前移让 findings 有消费者）
- FactBase key 前缀已含 owner（"基线模型表现" vs "结构化核心指标"），是 `as_fact_sheet` 把它盖掉的
- cross_chapter owner 对账用信号词表（纯正则，不需 LLM）：表现指标在正文 100% 带 owner 上下文

---

## 1. v13.0 内核契约层

v13.0 在 `agent/core/` 新增**契约层**，是 audit/constraint/guidance/eval/iteration/memory
协作的共同语言。旧模块通过适配器接入，不改内部逻辑。本层自身不依赖 agent 其他模块（零循环依赖）。

```
agent/core/
├── errors.py            # 错误分级 (Transient/Permanent/DegradedResult) + classify() 闸口
├── factbase.py          # FactBase 单一事实源（替代 PaperContext 写读分裂）
├── memory.py            # LayeredMemory 三层记忆 + get_or_compute() 缓存 + assemble(intent)
├── finding.py           # Finding 统一问题 + FindingBus 收集/查询/回流 + 4 适配器
└── figure_manifest.py   # FigureManifest 图清单（文图联动单一真相源）
```

| 契约 | 解决的旧病 | 接入点 |
|------|-----------|--------|
| errors | 42 处 except 静默降级 → 429 吞为 0图/0引用 | api_client._call_with_fallback + loop 8 处 |
| FactBase | auditor/verifier 各自从 project_data 重推导 → 数值分歧 | loop._build_paper_context + hierarchical_planner |
| LayeredMemory | citation_context 每章重注 7 次（10-30KB×7） | loop._build_citation_context 缓存包装 |
| Finding | 7 套不兼容 issue 结构（category/name/dimension/type/rule） | loop Phase 7.2 + quality_gate 修订链 |
| QualityLoop | QualityGate 内循环自封闭、不消费其他子系统 | loop._quality_ensure 注入 FindingBus 简报 |
| FigureManifest | 裸字符串拼接 + 无文图对账 + 占位图进正文 | （PR6 基础，注入迁移待 PR7） |

**设计原则**：收敛到少数契约，而非新增更多模块。7 套 issue → 1 套 Finding；
3 条渲染路径 → 1 条；42 处降级 → 分级。是在做减法和收敛。

> **v13.1 接线状态（P0 完成）**：审计后实测 v13.0 内核接线率仅 ~20%（5/6 块空转，
> 属"建了契约但下游不消费"的死接线）。v13.1 纯接线、零新模块：
> FindingBus 补 auditor/constraint/quality 3 个写入源（4 类问题合并回流修订）；
> FigureManifest 实例化并接通 `_generate_figures`/`_generate_latex_output`，
> 修复架构图双重注入 bug + 加 `validate_linkage` 文图对账。
> P1+P2 已完成（FactBase 接 auditor/verifier/cross_chapter 三消费者，verifier 真接入权威校验、cross_chapter 优先路径+dict 兜底、删 error_level/last_level 死代码）。
> **v13.1 P3 诚实取舍**：调研后两块都不接线，避免凑数：
> - **audit_with_autofix 删除**（90 行）：调研确认已被 QualityGate.evaluate_and_revise + FindingBus 回流（loop.py P0/P5）取代，复活=重复配额+双修订链打架。删而非复活。
> - **semantic_set/assemble 不做**：单独补写入点=纯死数据（0 消费者），必须三件一起大改（5 写入点+_run_chapter_phase 调 assemble+5 orchestrator 改读）且收益是换组装方式非真省 token（citation_context 已缓存）。留待有 token 超预算证据再做。

> **v13.2 产出瓶颈治理（基于实跑 Grade B 证据）**：
> - **#1 实验数据图闭环**：_build_figure_data 只用真实数据（FactBase/ablation_results/experiment_design 的真实数值），无真实数据返回 {} 触发 TikZ 示意诚实降级——绝不合成造假数值。figure_generator 的 data 路由已支持。
> - **#2 figure_planner 多图 fallback**：_default_plan 扩为 4 张骨架（teaser+module_detail+ablation+comparison），让 fallback 也达 TCSVT 主流配置 min_figures=4。**v15.5: plan 结果落盘 figure_plan.json 复用，且带 _source 标记（llm/fallback_model/default_4）让回落可观测。**
> - **#3 motivation 注入 ch1**：motivation_thread（已生成却从未进 prompt）注入 ch1 1.1 节。rationale/exemplar 暂不注入（ch1-5 无消费者=死代码）。
> - **#4 FindingBus 诊断埋点**：record_many 后加计数日志，待下次实跑据日志定位"0 条"根因（半完成，诚实标注）。
> audit_with_autofix 复活。7 套 issue → 1 套 Finding；
3 条渲染路径 → 1 条；42 处降级 → 分级。是在做减法和收敛。

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
  │ Phase 0 │→→→│ Phase 1~5   │→→│ Phase 6~9│
  │ 分析阶段│   │ 章节生成阶段│  │ 后处理   │
  └─────────┘   └─────────────┘  └──────────┘
```

**核心设计原则**：
- LLM 直出 LaTeX（不走 Markdown 中间格式）
- 代码 = 裁判，LLM = 运动员
- 零信任验证：每一步都校验，不信任 LLM 输出
- 全链路降级：每个外部依赖都有 fallback

---

## 2. 目录结构

```
paper-writing-assistant/
├── pipeline.py                  # 主入口
├── run_with_log.py              # 日志 Tee 包装器（文档化运行入口，保留）
│
├── config/                      # 配置层
│   ├── project_config.py        # 项目配置（标题、模型列表、阈值）
│   ├── api_config.py            # API 密钥 + Provider 配置 + 模型别名
│   ├── venue_profiles/          # 11 个期刊/会议场景配置
│   └── ieee_trans_style_profile.py  # IEEE Trans 写作风格硬规则
│
├── api/                         # API 客户端层
│   ├── openai_compatible.py     # 统一 OpenAI 兼容客户端（12+ Provider）
│   └── paper_search.py          # 论文检索（S2 语义搜索）
│
├── agent/                       # Agent 核心层
│   ├── core/                    # 🆕 v14 内核契约层（6 块契约，零循环依赖）
│   │   ├── errors.py            #   错误分级 (Transient/Permanent/DegradedResult) + classify()
│   │   ├── factbase.py          #   FactBase 单一事实源（替代 PaperContext 写读分裂）
│   │   ├── memory.py            #   LayeredMemory 三层记忆 + citation_context 缓存
│   │   ├── finding.py           #   Finding 统一问题 + FindingBus + 4 适配器
│   │   └── figure_manifest.py   #   FigureManifest 文图联动单一真相源
│   ├── loop.py                  # 自主循环引擎（系统心脏, v13: classify 闸口 + 8 处致命 except 分级）
│   ├── api_client.py            # 统一 API 客户端 (v13: classify 错误分级 + prompt 计数)
│   ├── dispatcher.py            # Leader-Worker 分层调度
│   ├── base_orchestrator.py     # LLM 调用基类 + 公共工具函数
│   ├── skill_orchestrators/     # 章节编排器（project_analyzer/ref_pdf/structure/ch1-5/...）
│   ├── venue_adapter.py         # 期刊适配器
│   ├── style_manager.py         # 统一风格管理 (P0 通用写作纪律层)
│   ├── quality_gate.py          # 质量门控 (v13: QualityLoop 接 FindingBus 简报)
│   ├── auditor.py               # 反幻觉审计引擎
│   ├── citation_manager.py      # 引用去重、编号
│   ├── cross_chapter_checker.py # 跨章节一致性检查 (读 FactBase 权威数值)
│   ├── hierarchical_planner.py  # 分层任务规划 (v13: 优先读 factbase.json)
│   ├── memory.py                # 双层记忆系统（旧，仅 THINK；生成走 core/memory.py）
│   ├── checkpoint.py            # 断点恢复
│   └── ...                      # 辅助模块
│
├── skills/
│   └── academic_writing_style/
│       ├── writing_discipline.md # P0 跨期刊通用写作纪律 (10条规则)
│       └── style_guide.md        # P3 IEEE 特有写作规范
│
├── tools/                       # 工具层
│   ├── latex_converter.py       # LaTeX 组装 + LLM 审查修复 + 中文字符过滤
│   ├── latex_constraint_checker.py  # 编译前结构合规审计
│   ├── bibtex_builder.py        # BibTeX 生成（模板组装）
│   ├── arch_diagram_renderer.py # 架构图渲染 (v13: 视觉评价真重渲闭环)
│   ├── figure_planner.py        # 图表规划
│   ├── figure_generator.py      # TikZ 图表生成 (LLM 产规格 + 自愈编译)
│   ├── result_visualizer.py     # 实验结果可视化
│   ├── output_evaluator.py      # L1/L2/L3 三层评价
│   ├── pdf_compiler.py          # XeLaTeX 编译
│   ├── pdf_validator.py         # PDF 验证 + 溢出修复
│   └── ...
│
├── figure/                      # 图表模板（v13 清理后仅保留活依赖）
│   ├── style_templates.py       #   期刊风格模板（data_visualizer 3 处 import）
│   ├── layout_engine.py         #   TikZ 布局引擎（测试引用）
│   └── layout_templates.py      #   管道/分支模板（测试引用）
│
├── test/                        # pytest 测试（v13 清理后 7 个有效模块，263 测试 0 error）
│   ├── conftest.py              #   pytest 配置
│   ├── test_systemic_upgrade.py #   (39) / test_v10_1_smoke.py (26)
│   ├── test_citation_multisource.py  # (24) / test_v9_2_figure_system.py (6)
│   ├── stage_targeted_test.py   #   (4) / test_pdf_validator.py (4) / test_phase85_quick.py (1)
│
└── data/                        # 离线数据
    └── reference_packs/         # 离线论文
```

> **v13.0 清理记录**：两轮保守删除共 15 个死代码/废弃测试（每点 grep 验证 0 引用）。删 4 个废弃 figure 渲染器（architecture_renderer/ablation_plotter/comparison_plotter/teaser_designer）、3 个根级废弃脚本（test_batch1/test_v9_2/test_v9_3）、8 个废弃测试（2 坏 + 6 一次性 `__main__` 脚本）。活依赖（style_templates/layout_engine/layout_templates/run_with_log）保留。

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
| VERIFY | 8 项纯代码检查（引用/数据/公式/去重/标记/结构/符号） | 否 |
| REFLECT | LLM 评估结果质量，更新记忆，决定下一步 | 是 |

---

## 4. Phase 流水线

### 4.1 Phase 0 — 分析阶段

| Phase | 名称 | 模块 | 功能 |
|-------|------|------|------|
| 0.1 | 工程代码分析 | `project_analyzer.py` | 扫描 PROJECT_CODE_PATH，提炼创新点/模型架构/实验设计 |
| 0.2 | 参考论文分析 | `ref_pdf_analyzer.py` | 加载 ref_md/（Markdown 优先）或 ref_pdf/（PDF 解析），提取写作风格/章节组织 |
| 0.3 | 领域信息提取 | `ref_pdf_analyzer.py` | 从参考论文中提取领域知识（术语、数据集、指标） |
| 0.5 | 全局大纲规划 | `structure_planner.py` | 生成 outline.json（子节划分 + 内容清单 + 篇幅预算） |
| 0.6 | 范例学习 | `exemplar_learner.py` | 6 层阅读协议，从参考论文深度学习写作决策 |
| 0.65 | 内容策略规划 | `content_strategist.py` | 为每章规划 must_include / focus_areas / should_avoid |
| 0.7 | 写作理由矩阵 | `rationale_matrix.py` | 事前规划型矩阵（Motivation / SOTA Gap / Scenario / Evidence） |
| 0.8 | 期刊风格学习 | `journal_style_learner.py` | 10 层协议，学习期刊特有写作模式 |
| 0.9 | 动机引擎 | `motivation_engine.py` | 强制确认论文动机后才允许写作 |
| 0.95 | 参考论文搜索 | `ref_search_strategist.py` | 精准收束逐层放宽搜索参考论文 |

### 4.2 Phase 1~5 — 章节生成

| Phase | 章节 | 编排器 | LLM 调用次数 |
|-------|------|--------|------------|
| 1 | Introduction | `ch1_introduction.py` | 3（1.1 背景 + 1.2 局限 + 1.3 贡献） |
| 2 | Related Work | `ch2_related_work.py` | 4~5（3 子节 + 总结过渡） |
| 3 | Methodology | `ch3_methodology.py` | 4~6（3.1 总览 + N 模块 + 损失函数） |
| 4 | Experiments | `ch4_experiments.py` | 4（数据集 + 实现 + SOTA + 消融） |
| 5 | Conclusion | `ch5_conclusion.py` | 1 |

**每章生成后自动执行**：
1. `_quick_audit()` — 快速审计（格式/引用/公式检查）
2. `_quality_ensure()` — 质量门控（不达标则自动修订，最多 3 轮）
3. 章节级状态机：`outline → draft → review → revision → final`

### 4.3 Phase 6~9 — 后处理

| Phase | 名称 | 模块 | 功能 |
|-------|------|------|------|
| 6 | 参考文献审查 | `reference_checker.py` | 验证引用可检索性和出处真实性 |
| 6.5 | 反幻觉审计 | `auditor.py` | 逐步验证 + 参考文献反向检索 + 内容真实性校验 |
| 7.0 | 全局打磨 | `loop.py` | 修正常见表述问题 |
| 7.1 | 引用解析 | `citation_manager.py` | 🆕 按 chapters dict 独立处理 `<citation>` → `[N]`（无 join-then-split） |
| 7.15 | 有序门控 | `ordered_gate.py` | P0 格式 → P1 一致性 → P2 写作质量 (v12.2: verify_all 只调用一次) |
| 7.2 | 跨章节检查 | `cross_chapter_checker.py` | 🆕 基于 PaperContext 数值矛盾自动修复，返回 (issues, fixed_chapters) |
| 7.3 | LaTeX 组装 | `latex_converter.py` | 章节合并 → LLM 审查 → 模板填充 → 中文字符过滤 |
| 7.35 | citation 清理 | `loop.py` | 🆕 tex 后 `<citation>` 残留正则清理（Phase 7.3 LLM review 兜底） |
| 7.8 | BibTeX 生成 | `bibtex_builder.py` | `[N]` → `\cite{key}` 替换 + BibTeX 条目生成 |
| 7.9 | 约束预检 | `latex_constraint_checker.py` | 编译前结构合规审计 |
| 8 | PDF 编译 | `pdf_compiler.py` | XeLaTeX 编译 |
| 8.5 | PDF 验证 | `pdf_validator.py` | Overfull 检测 + 自动修复 + 重编译 |
| 9 | 输出评价 | `output_evaluator.py` | L1 格式 + L2 完整度 + L3 学术质量 |

---

## 5. 核心模块设计

### 5.1 API 客户端（降级链）

```
调用请求
   │
   ↓
┌──────────────────────────────────────────────┐
│          api_client.py (UnifiedAPIClient)     │
│                                               │
│  GENERATION_MODELS 降级链:                     │
│  tp_qwen3_7_max → glm_5_1 → glm_4_7 →        │
│  tp_deepseek_v4_pro → tp_qwen3_6_plus → ...   │
│                                               │
│  每个 Provider 最多重试 2 次                    │
│  失败后自动切换到下一个模型                      │
│  全部失败则抛出 AllModelsExhausted              │
└──────────────────────────────────────────────┘
```

**三级模型分层**：

| 用途 | 模型列表 | 调用方法 |
|------|---------|---------|
| 生成（主力） | tp_qwen3_7_max, glm_5_1, ... | `call_generation()` |
| 推理/决策 | tp_qwen3_7_max, glm_5_1(thinking), ... | `call_reasoning()` |
| 轻量任务 | tp_qwen3_6_flash, tp_deepseek_v4_flash | `call_light()` |

**评价模型隔离**：评价模型必须与执行模型来自不同 Provider（避免"自我审查"盲区），由 `resolve_eval_models()` 动态解析。

**Provider 体系**：

| Provider | SDK | 模型 |
|----------|-----|------|
| zhipu (智谱) | zai SDK (ZhipuAI) | glm_5_1, glm_5, glm_4_7 (thinking), glm_4.6v, glm_4.5v |
| aliyun_token_plan | OpenAI 兼容 | tp_qwen3_7_max, tp_qwen3_6_plus, tp_deepseek_v4_pro/flash |
| aliyun_bailian | OpenAI 兼容 | qwen3_7_max, qwen3_6_plus |
| openai | OpenAI SDK | gpt_5_5, gpt_5_4, gpt_5_3 |

### 5.2 LLM 调用基类

```
base_orchestrator.py (BaseOrchestrator)
├── call_generation(prompt)    → 生成模型
├── call_reasoning(prompt)     → 推理模型（带 thinking）
├── call_light(prompt)         → 轻量模型
├── call_evaluation(prompt)    → 评价模型（跨 Provider）
├── parse_json_with_retry()    → JSON 解析（3 次重试）
├── save_output()              → 保存到 output/
└── build_style_instruction()  → 统一风格指导构建
```

### 5.3 LaTeX 组装（v12.0 架构）

```
Chapter Prompt (原生 LaTeX)
       │
       ↓
┌─────────────────────────┐
│ _minimal_cleanup()      │  清理 [?]、空 section、Markdown 残余
│ [不删 <citation> 标记]  │  ← 关键：留给 Phase 7.8 替换
└──────────┬──────────────┘
           │
           ↓
┌─────────────────────────┐
│ _review_latex()         │  LLM 审查 1 轮（花括号/环境配对/表格格式）
└──────────┬──────────────┘
           │
           ↓
┌─────────────────────────┐
│ assemble_latex_paper()  │  模板填充 + TikZ 注入 + 后处理修复链
└──────────┬──────────────┘
           │
           ↓
   output/latex/main.tex
```

**后处理修复链**（内置于 `latex_converter.py`）：
1. `_fix_textwidth_confusion()` — 修复 `\textwidth` / `\columnwidth` 混用
2. `_ensure_table_resizebox()` — 确保表格有 `\resizebox` 包裹
3. `_ensure_tikz_fits()` — TikZ 图片尺寸适配
4. `_validate_float_sizing()` — 浮动体尺寸验证
5. `_fix_long_equations()` — 长公式换行修复

### 5.4 引用处理流水线

```
LLM 输出 <citation>["keyword"]</citation>
       │
       ↓ Phase 7.1 (v12.0: chapters dict 接口)
citation_manager.py: run_citation_manager_for_chapters()
  ├─ 按 chapter key 独立 collect <citation> 标记
  ├─ 汇总统一 verify + dedup（全局唯一连续编号）
  └─ 按 chapter key 独立 resolve → 更新 chapters dict
       │
       ↓ Phase 7.2 (v12.0: PaperContext 自动修复)
cross_chapter_checker.py: check_all() → (issues, fixed_chapters)
       │
       ↓ Phase 7.3
latex_converter.py: 组装 + _minimal_cleanup() (含中文字符过滤)
       │
       ↓ Phase 7.35 (v12.0: 兜底清理)
loop.py: <citation> 残留正则清理
       │
       ↓ Phase 7.8
bibtex_builder.py: [N] → \cite{ref_N} 替换 + 生成 references.bib
```

### 5.5 PaperContext 共享事实源 (v12.2: 磁盘持久化 + 双路修复)

```
Phase 0.98: _build_paper_context()
       │
       ↓ 从 project_data + experiment_design 提取
paper_context = {
    "hardware": "1x RTX 3090",
    "training_params": {"epochs": 100, "batch_size": 8},
    "loss_terms": ["L_photo", "L_smooth", "L_depth"],
    "datasets": ["HCI 4D", "Stanford Lytro"],
    "metrics": {"MAE": 0.133, "MSE": 0.081},
    "model_name": "GeoDualMask-Net",
    "innovation_names": ["Dual-Branch", "Geometry-Aware Attention"],
}
       │
       ├─→ 注入 self._project_data["paper_context"]
       │     └→ 各 chapter generator 通过 citation_context 自动获得
       │
       ├─→ v12.2: 持久化到 output/paper_context.json
       │     └→ ValidationEngine._read_paper_context_exists 验收通过
       │
       └─→ 注入 CrossChapterChecker
             └→ v12.2: 双路数值修复
                 ├─ PaperContext metrics（权威源）
                 └─ Experiments "Ours" 行提取值（兜底）
```

### 5.6 风格系统层级 (v12.0)

```
StyleManager._get_academic_rules(chapter):
  │
  ├─ P0: writing_discipline.md
  │     跨期刊通用写作纪律（10条规则）
  │     信息密度 / 逻辑衔接 / tone / 禁用词 / Oxford 引用
  │
  ├─ P3: style_guide.md (IEEE 特有)
  │     词汇规则 / 禁用词表
  │
  ├─ P5: style_guide.md
  │     清理规则
  │
  ├─ 章节特定规则 (hardcoded fallback)
  │
  └─ IEEE Trans 规则 (从 venue_profile)
```

### 5.5 评价体系（L1/L2/L3）

| 层级 | 名称 | 分数权重 | 检查方式 | 通过标准 |
|------|------|---------|---------|---------|
| L1 | 格式有效性 | 10% | 正则匹配 | IEEEtran 模板、abstract/keywords、表格/图片/公式数量 |
| L2 | 内容完整度 | 35% | 正则匹配 | 5 章齐全、词数 ≥ 3000、引用 ≥ 20、公式 ≥ 5、消融 ≥ 3 |
| L3 | 学术质量 | 55% | LLM 分段审稿 | 分段摘要 → 全局审稿（创新性/严谨度/写作风格等 8 维度） |

**评级公式**：`avg = L1×0.1 + L2×0.35 + L3×0.55`
- A ≥ 80, B ≥ 65, C ≥ 50, D < 50

---

## 6. 降级链设计

### 6.1 API 降级

```
请求 → Provider A 模型 1
              ↓ 失败/超时
        Provider A 模型 2
              ↓ 失败/超时
        Provider B 模型 1
              ↓ 失败/超时
        ...
              ↓ 全部失败
        AllModelsExhausted 异常
```

### 6.2 学术搜索降级

```
搜索请求 → 离线数据包 (data/reference_packs/*.json)
              ↓ 无结果
          academic_search API (ustc-ai4science)
              ↓ 超时（境内不可用）
          paper_search.py (S2 语义搜索)
              ↓ 超时
          返回空结果，LLM 基于领域知识自行补充
```

### 6.3 参考论文加载降级

```
load_ref_papers() → ref_md/*.md (Markdown 全文)
                       ↓ 无文件
                   ref_pdf/*.pdf (PyMuPDF/pdfplumber/PyPDF2)
                       ↓ 无文件
                   paper-fetch 在线获取 (DOI → Markdown)
                       ↓ 超时
                   返回空列表
```

### 6.4 风格指导构建降级

```
build_style_instruction() → VenueAdapter (StyleManager)
  │                              │
  │  P0: writing_discipline.md (跨期刊通用写作纪律)
  │  P3: style_guide.md (IEEE 特有词汇规则)
  │  P5: style_guide.md (清理规则)
  │  章节特定规则 (hardcoded fallback)
  │  IEEE Trans 规则 (从 venue_profile)
  │
  └─→ 失败时降级链:
      IEEE Trans Style Profile (硬规则)
          ↓ 失败
      skills/academic_writing_style/style_guide.md
          ↓ 失败
      最小化默认规则
```

### 6.5 BibTeX 生成降级

```
BibTeX 请求 → Phase 7.1 citation_map 映射
                 ↓ 不足 5 条
             独立构建（从 citation_bank 遍历）
                 ↓ 查询失败
             Python 模板兜底组装（100% 成功率）
```

### 6.6 LLM 评价降级

```
L3 评价请求 → call_evaluation() (跨 Provider 评价模型)
                 ↓ 失败
             call_generation() (同 Provider 生成模型兜底)
```

---

## 7. 关键设计决策

### 7.1 v12.0 架构变更：LLM 直出 LaTeX

**旧架构**（v11.x）：
```
LLM → Markdown → 500 行正则转换 → LaTeX  [bug 工厂]
```

**新架构**（v12.0）：
```
LLM → 原生 LaTeX → LLM 审查 → 编译 → 反馈修复 (最多 2 轮)
```

**变更原因**：正则转换是级联 bug 的根源——Markdown 的模糊语法（列表/嵌套/表格）无法被正则可靠处理。

### 7.2 代码 = 裁判，LLM = 运动员

- `ordered_gate.py`：纯代码的门控流水线，不依赖 LLM 判断
- `auditor.py`：正则 + 规则引擎的反幻觉审计
- `output_evaluator.py`：L1/L2 纯正则，只有 L3 用 LLM

### 7.3 章节级状态机

```
outline ──→ draft ──→ review ──→ revision ──→ final
   │          │         │          │            │
   └── 跳过 ──┘         │          │            │
                        └── 不通过 ─┘            │
                                    └── 最多 3 轮 │
                                                 │
                                           质量达标 ✓
```

### 7.4 恒定大小上下文

`bounded_context.py` 管理 3 层记忆，总预算 5000 字符：
- **工作记忆**：当前正在处理的信息
- **短期记忆**：最近 N 个 Phase 的摘要
- **长期记忆**：持久化的关键结论（磁盘存储）

### 7.5 v12.2 章节生成统一分发 (Wave 6 重构)

```python
_CHAPTER_CONFIGS = {
    1: ("ch1_introduction", "Introduction"),
    2: ("ch2_related_work", "Related Work"),
    3: ("ch3_methodology", "Methodology"),
    4: ("ch4_experiments", "Experiments"),
    5: ("ch5_conclusion", "Conclusion"),
}
# phase1-phase5 统一通过 _run_chapter_phase(ch_num) 分发
# 消除了 5 个重复的 if/elif 块（~80 行）
```

Wave 6 同时将 `_run_output_phase`（664 行）拆分为 5 个子方法：
- `_postprocess_content()` — 全局打磨 + 门控 + 一致性 + 公式 + 去重
- `_generate_figures()` — 图表规划 + 生成
- `_generate_latex_output()` — LaTeX/BibTeX/约束预检
- `_run_table_fallback()` — 表格兜底
- `_compile_and_validate()` — PDF 编译 + 验证 + 分层验收 + 评价

### 7.6 v12.2 系统性 Bug 修复

| 问题 | 根因 | 修复 |
|------|------|------|
| ch5 Conclusion 仅输出 2 词 | f-string 中 `\begin{X}` 的 `{X}` 被解释为替换字段 → NameError → 异常被 try/except 静默捕获 → 返回 2 词降级字符串 | `\\begin{{X}}` 转义（与 ch1-ch4 对齐） |
| PaperContext 验收失败 (G3-S6) | `_build_paper_context` 只更新内存，不写磁盘 → `_read_paper_context_exists` 读磁盘文件返回 0 | 构建后 `json.dump` 到 `paper_context.json` |
| 禁用术语永不修复 | `should_retry` 被分数判断覆盖（line 244 覆盖 line 230） | 改为 `score_based_retry OR issue_based_retry` |
| 数值矛盾修复静默失效 | `_find_canonical_value` 只查 PaperContext，`ours_values` 参数是死代码 | 双路查找：PaperContext metrics → Experiments ours_values 兜底 |
| VenueAdapter 风格丢失 | 章节生成器各自 `VenueAdapter()` 新建实例 → `_journal_style` 丢失 | v12.3: 依赖注入参数链（替代 v12.2 的类级属性方案） |
| ordered_gate verify_all 重复调用 | Gate 0 和 Gate 1 各自调用 `verify_all()` | `run()` 中调用一次，传入两个 Gate |
| content_strategy/motivation_thread 未消费 | `_run_chapter_phase` 不注入这些 Phase 0.65 的分析结果 | 注入 `self._project_data` 供章节生成器读取 |

### 7.7 Wave 1-6 代码瘦身记录

| Wave | 内容 | 删除行数 |
|------|------|---------|
| 1-5 | 删除 13 个废弃模块（chapter_state_machine, exceptions, serper_normal, tavily_normal, webpilot_wattpro, ablation_runner, data_source_manager, iterate_controller, latex_direct_generator, paragraph_controller, ref_pdf_downloader, scholar_search, tikz_generator） | ~3,000 |
| 6 | loop.py 重构：`_CHAPTER_CONFIGS` 统一分发 + `_run_output_phase` 拆分（664→36 行） + 提取 7 个子方法 | ~700（净减） |

### 7.8 v12.3 架构净化 — PipelineContext + 依赖注入

#### PipelineContext（单一真相源）

```
agent/pipeline_context.py
├── PipelineContext (dataclass)
│   ├── project_data, ref_data          # Phase 0 核心数据
│   ├── chapters, abstract              # 生成的内容
│   ├── reference_pool, outline         # 预生成分析
│   ├── motivation_thread               # 动机驱动
│   ├── exemplar_dossier, style_profile # 范文学习
│   ├── citation_bank, rationale_matrix  # 引用/论证
│   ├── ablation_results                # 消融实验
│   ├── journal_style, content_strategy # 学习到的风格
│   ├── paper_context                   # 验证上下文
│   └── cite_key_map, title_to_key      # 引用映射
│
├── to_checkpoint_dict() / from_checkpoint_dict()  # 序列化
└── save_to_checkpoint() / load_from_checkpoint()  # CheckpointManager 集成
```

**集成方式**：ResearchLoop 类级属性代理（`_ctx_property`），将 17 个 `self._xxx` 透明路由到 `self.ctx.xxx`。现有代码无需修改，新代码直接使用 `self.ctx.xxx`。

#### 依赖注入参数链（VenueAdapter）

```
ResearchLoop.__init__     →  self.venue_adapter = VenueAdapter()   # 唯一实例
    ↓
_run_chapter_phase        →  kwargs["venue_adapter"] = self.venue_adapter
    ↓
run_chapterN(..., venue_adapter=...)
    ↓
generate_*(..., venue_adapter=...)
    ↓
build_style_instruction(..., venue_adapter=...)   # 不再 VenueAdapter() 新建
```

**关键变化**：
- `base_orchestrator.py:build_style_instruction` 接受 `venue_adapter` 参数，不再每次 `VenueAdapter()` 新建
- `ch5_conclusion.py` 使用统一的 `build_style_instruction`（不再自建 VenueAdapter + IEEE 降级链）
- `venue_adapter.py` 的 `_journal_style` / `_ref_style_guide` 回退为实例属性（不再是类级共享）

---

## 8. 配置体系

### 8.1 期刊 Profile 系统

```
config/venue_profiles/
├── base_profile.py       # 基类 + dataclass 定义
├── __init__.py            # Profile 注册表 + get_profile()
├── journal_csvt.py        # IEEE TCSVT
├── journal_tip.py         # IEEE TIP
├── journal_tpami.py       # IEEE TPAMI
├── journal_ijcv.py        # IJCV
├── journal_pr.py          # Pattern Recognition
├── journal_displays.py    # Displays
├── conf_cvpr.py           # CVPR
├── conf_iccv.py           # ICCV
├── conf_eccv.py           # ECCV
├── conf_aaai.py           # AAAI
└── conf_neurips.py        # NeurIPS
```

每个 Profile 定义：引用数阈值、公式/表格/图片最低数量、消融实验要求、篇幅预算、禁用术语等。

> **⚠️ 技术债**：当前 Profile 用 Python class 实现（~1650 行纯数据声明）。
> 本质是指引+约束，应迁移为 **Markdown 文件**（阈值用表格，指引用正文）。
> 原因：Profile 一半给代码读（阈值），一半给 LLM 读（指引），
> Markdown 天然就是 LLM 的食物，无需 `to_prompt_block()` 转换。
> YAML 是多余的中介 — 多一层序列化，没解决"LLM 直接消费"的核心需求。

### 8.2 关键阈值（TCSVT 默认值）

| 参数 | 值 | 用途 |
|------|---|------|
| `min_references` | 25 | L2 引用最低数量 |
| `min_formulas` | 5 | L2 公式最低数量 |
| `min_tables` | 3 | L2 表格最低数量 |
| `min_figures` | 3 | L2 图片最低数量 |
| `min_ablations` | 3 | L2 消融提及最低次数 |
| `quality_threshold` | 72.0 | 质量门控阈值 |
| `max_review_rounds` | 3 | 章节最大修订轮次 |

---

## 9. 数据流图

```
PROJECT_CODE_PATH/          ref_md/ + ref_pdf/
  ├── *.py (模型代码)         ├── paper1.md
  ├── *.md (报告/README)      ├── paper2.pdf
  ├── config.yaml             └── ...
  └── IDEA_REPORT.md
         │                          │
         ↓                          ↓
  ┌──────────┐              ┌──────────────┐
  │ Phase 0.1│              │  Phase 0.2   │
  │ 代码扫描 │              │ 参考论文分析 │
  └────┬─────┘              └──────┬───────┘
       │                           │
       ↓                           ↓
  innovation_points.json     style_guide.json
  model_architecture.json   chapter_organizations.json
  experiment_design.json    domain_info.json
       │                           │
       └───────────┬───────────────┘
                   ↓
           Phase 0.5~0.95 (规划)
                   ↓
            outline.json + 各策略
                   │
       ┌───────────┼───────────┐
       ↓           ↓           ↓
  Phase 1~5   (章节 LLM 生成)
       │           │           │
       ↓           ↓           ↓
  output/chapter1~5/*.md  (原生 LaTeX 内容)
                   │
                   ↓
         Phase 7 (后处理组装)
                   │
       ┌───────────┼───────────┐
       ↓           ↓           ↓
  main.tex    references.bib   full_paper.pdf
                   │
                   ↓
         Phase 9 (L1/L2/L3 评价)
                   │
                   ↓
          evaluation_report.json
```

---

## 10. 运维

### 启动

```bash
# 标准启动（从头开始）
python run_with_log.py --no-resume

# 从断点恢复
python run_with_log.py

# 覆盖配置
python run_with_log.py --title "My Paper Title" --code-path /path/to/code
```

### 运行中干预

编辑 `output/HUMAN_DIRECTIVE.md` 文件即可在运行中干预 Agent 方向。

### 输出

```
output/
├── latex/main.tex          # 最终 LaTeX 源码
├── latex/references.bib    # BibTeX 引用
├── full_paper.pdf          # 编译后的 PDF
├── evaluation_report.json  # L1/L2/L3 评价结果
├── audit_detail.json       # 审计详情
├── chapter1~5/             # 各章中间文件
└── memory_state.json       # 记忆状态（断点恢复用）
```


## 八、PaperJury 统一评价范式（v14 最终）
一个评价范式（paperjury），两个时机（生成时+终局），一个修订闭环（QualityGate）。
生成阶段 QualityGate evaluate 用 paperjury 两轮审稿（issues + evidence_anchor + close_criterion）。
终局 L3 同范式确认，close_criterion 写报告。删了 _l3_revise_loop（架构不合理的第二套修订）。
