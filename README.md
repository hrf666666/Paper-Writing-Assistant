# 论文范文写作助手 v16.2 (Paper Writing Assistant)

一个基于多个大语言模型的智能顶刊论文范文写作系统，采用 **THINK → EXECUTE → VERIFY → REFLECT** 自主循环架构。**v14.0 引入内核契约层 + paperjury 对抗式审稿范式**（错误分级 / FactBase 单一事实源 / 分层记忆 / Finding 统一问题总线 / QualityLoop 真闭环 / FigureManifest 文图联动），让 audit/constraint/guidance/eval/iteration/memory 通过少数契约协作，而非各自为政的松散机制。**v15.5-v15.7 治愈引用漂移/figure 非确定性/文图联动断裂**。**v15.8-v16.1 建立数值可信三道防线（真相注入+写后检测+带真相段落重写）+ FixAction executor + warning 可见化**。**v16.2 架构升级：pipeline 从线性（生成→检测→报告）变成闭环（边写边改+全文检查闭环），L3 从终局评价变成闭环检测器**。系统能够根据**文章类型 + 论文标题 + 项目实验工程代码**，自动生成完整的5章+摘要学术论文（LaTeX 或 Word），作为写作参考或起点。

## v16.2 里程碑：边写边改 + 全文检查闭环（架构升级）

> **v16.2 统一了 v15.5-v16.1 的碎片防线——不是加第6道防线，是把校验嵌入生成过程 + L3 接回闭环。** 所有问题的共同根：论文声称 vs 真相源不一致。v16.2 改变了 pipeline 拓扑（线性→闭环），3 个模块 + 3 个接线（~340 行）：
> - **模块A 统一真相上下文**（`truth_context`）：合并 architecture/experiment 真相 + 自动矛盾标注（零参数+SAM 同现→标注），经 planning_block 自动注入所有章节 prompt。token 预算≤9KB。
> - **模块B 子节即时校验**（`_verify_chapter_subsections`）：orchestrator 返回整章后按 \n\n 切分子节，逐个确定性正则校验（cite/数值/图引用），有错带真相重写。零 LLM 调用（只有检测到错才调）。
> - **模块C L3 闭环重写**（`_run_l3_revision_loop`）：L3 major issues → evidence_anchor 定位段落 → 带真相重写 → 重新生成 main.tex。L3 从"终局评价"变成"闭环检测器"。+ 引用链验证（cite→bib title 一致性）。
> - **为什么不蠢**：不靠正则提取语义声称（蠢）→ 靠 L3 理解语义（完备）；不在文本上机械替换（蠢）→ 带真相理解性重写；不外挂检查器（解耦）→ 校验嵌入生成+L3 接回闭环。
> - **诚实的局限**：实验缺陷类问题（整体退步/Non-Lamb 持平）不可修——架构能让论文"忠实反映真相"，但不能"改变真相"。

## v16.1 里程碑：带真相的段落级重写（第三道防线）

> **v16 建了前两道防线（真相注入+写后检测），但检测到的错误修正不了。v16.1 补第三道防线。**
> - 段落级重写（`_revise_paragraphs`）：检测到数值张冠李戴 → 定位出错段落 → 把 FactBase 真相+错误描述拼给 LLM → 只重写这段。实跑验证：ch1 修正 0.411 标 urban→non-lambertian，ch5 修正 0.081 标 urban→mixed。
> - 三道防线完整：防线1（真相注入）→ 防线2（写后检测）→ 防线3（带真相段落重写）。

## v16 里程碑：数值可信——补"可用参考稿"缺失的核心一环

> **回到系统初衷：产出可信的参考稿。** cite 有两道防线（写前约束+写后校验），数值没有。v16 给数值加上同样的两道防线。
> - **防线1**（`_compute_pairing_constraint`）：FactBase 配对约束——按子集列出 ours/baseline 值，让 LLM 看到每个数值的正确归属。张冠李戴 21→2 处。
> - **防线2**（`_validate_metric_attribution`）：编译前扫描正文数值归属，检测张冠李戴记入 findings_report。
> - bug 修复：重复 end{document}（replace 漏 count=1）+ 留痕切断文字（offset 替换→批量字符串替换）。

## v15.9 里程碑：FixAction executor + 不可修 warning 可见化

> **系统性问题诊断：warning 死信。** FindingBus 的 warning finding 从不被消费（只有 critical 触发 rerun），5+ 个检测器共享此缺陷。
> - FixAction executor（`_apply_auto_fixactions`）：Phase 5.6 后自动执行 auto_apply 的 replace_number FixAction，降级 severity 避免重复。
> - 不可修 warning 可见化（`_dump_findings_report`）：落盘所有 warning+ findings 到 findings_report.json。
> - 核心设计：确定性的事让代码做（executor），语义的事让 LLM 做（hint），做不到的事让人看到（落盘）。

## v15.8 里程碑：弱点一致性闭环 + 留痕 bug + overclaim 扩展 + FactBase 对比结论

> **E3+L3 issue[2]/[3] 的统一诊断：叙事分裂**（abstract 声称优越但 Limitations 承认退步，两者不同步）。
> - 留痕 bug 修复（v15.5 的 `\textbf{[REF?]}` 放 cite 内部破坏 LaTeX → 整条 cite 替换）。
> - overclaim 扩展（新增"零参数+SAM"能力夸大检查）。
> - FactBase 对比结论（`_compute_comparison`）：预计算 ours vs baseline 胜负，Overall 退步时警告"禁止声称整体优越"。
> - abstract 注入 Limitations + FactBase（弱点一致性闭环）。
> - cross_chapter 跨章节同指标一致性检查。

## v15.7 里程碑：文图联动治本（规划前移 + 通信回路）

> **v15.7 解决地基级问题——文图联动通信断裂**。v14 引入 FigureManifest 时承诺"文图联动单一真相源"，但 figure_planner 在 Phase7.28（章节后）规划，结果从未流入章节生成，导致 7 张图全 orphan（正文从不 \ref）。经三圈推理排除臃肿方案（粗+精二次规划/图归章节/prompt硬编码），定位问题本质是**通信断裂**而非归属之争。
>
> **解法（4 处改动 ~60 行，零章节签名改动）**：
> - **规划前移**（phase0_99）：plan_figures 在章节前用 abstract+innovation 规划（method_text 空，章节未生成），写 figure_plan.json + 填 manifest(PLANNED) + 构建 figure_directives 塞 project_data
> - **通信回路**（planning_block）：ChapterContext.planning_block 读 figure_directives，按 _TYPE_TO_SECTION 拼引用指令注入章节 prompt——复用 v14 已有的 planning_block 注入范式，**不改任何章节签名/prompt**
> - **Phase7.28 复用**：ablation_hash 一致使 Phase7.28 读到前移 plan 不重新规划；manifest add→update 避免 duplicate；渲染前用成品 method 补粗糙 caption
> - **验证**：5 章全部调用 planning_block 且 _planning 注入 prompt → figure 指令自动通达所有章节
>
> **为何不臃肿**：一次规划（非二次）、零签名改动（合并进 planning_block）、用 manifest 已有 add/update 方法（非新状态机）。268 测试全过。
> - **推迟**：E3 数值矛盾（需 FactBase 条件溯源）+ L3 稳定性 + G4 字数闭环

## v15.6 里程碑：4 个实跑后深挖根因修复

> **v15.6 来自 v15.5 实跑的综合分析**——逐个挖到代码行级根因，反思"为何历史 review 漏检"。4 项修复（~80 行），无架构改动：
> - **E1 图墙时序错位**：v15.4 #3 只认 `\bibliographystyle` 锚点，但 Phase 7.3 时刻 tex 是 `thebibliography`（要等 7.8 才转换）→ 图插在参考文献后堆成"图墙"。修复：锚点列表优先级匹配（thebibliography/bibliographystyle/bibliography）+ 位置校验扩展。
> - **E2 None 污染**：`str(p.get("year"))` 当 year=None 产出 "None" 字符串 → heNone 畸形 key 污染真相源；surname 取末位作者（He）而非首作者（Wang）。双 bug 叠加。修复：year 显式类型判断 + surname 取首作者姓。
> - **E4 overclaim 反向校验**：auditor 原只查"应提未提"（正向遗漏），不查"凭空包装"（负向 overclaim）。修复：新增 `_check_method_overclaim`，抓"基于X理论"表述对照真实代码（loss/model_content），L2 不再冒充 Maxwell 力学。
> - **E5 validator 矢量图识别**：pdf_validator 只数文字面积，TikZ/pgfplots 矢量图（get_images 检不到）页被判空白。修复：用 get_drawings() 识别矢量图，有图页不算空白；valid 判定不再被 coverage 阈值误杀。
> - **反思**：4 个漏检归因三个结构性盲区——逻辑正确≠时序正确（E1）、默认值兜不住None（E2）、验收标准定在"能跑通"非"真达标"（E5）。
> - **推迟 v15.7**：E3 数值矛盾（需 FactBase 加实验条件溯源，属架构改动）。

## v15.5 里程碑：引用前置校验门 + figure plan 固化

> **v15.5 治愈两个系统性问题**——根因都来自 v15.3 后的 6/22 vs 6/23 对照实测。两次运行的 `undefined_cite_keys` 与缺图（6/23 回落到 3 张 default plan）暴露：cite key 仅靠 prompt 祈使句约束 + Phase 7.8b 事后静默删；figure plan 每次 LLM 现规划不落盘。2 项改动（~120 行）：
> - **A1 引用前置校验门**：`_validate_cite_keys` 在 Phase 7.8 写盘后先跑——合法 key 通过、同 surname+年份差≤1 的笔误 fuzzy 修正、编造 key（如 `urbanlf_dataset`）改为 `[REF?]` 留痕（不再静默删，保留可见性）。Phase 7.8b 的"删 cite"分支删除。
> - **A2 figure plan 固化**：`plan_figures` 结果落盘 `figure_plan.json`（带 `_source`/`_ablation_hash`），后续读盘复用——checkpoint resume 不再重规划；`_default_plan` 从 3 张升级 4 张（+module_detail）；plan 来源（llm/fallback/default_4）可观测。
> - **推迟到 v15.6**：L3 评价稳定性（离散计数抖动）+ G4 Conclusion 字数闭环（需动评价范式，风险大）。

## v15.3 里程碑：评价可信化 + 数值 owner 真相源 + 前移闭环

> **v15.3 核心突破**——治愈 v14 评价模块的诊断→改进断裂。根因是 `as_fact_sheet` 一行代码把 baseline 数值标成 "Ours 权威值"（3 环节连环放大），导致 LLM 误用 baseline 值 + cross_chapter 查"存在性"非"语义" + FindingBus 后半程无消费者。4 层 11 项改动（~220 行，无新模块）：
> - **L0 评价可信化**：L1/L2 去重（公式/表/图不再双倍扣分）+ 阈值按字数缩放（短论文不再误判）+ conclusion 定位用 `\section` 而非 `[-5000:]` 窗口
> - **L1 owner 真相源**：as_fact_sheet 按 owner 分组渲染（ours vs baseline）+ training_params 进 FactBase + cross_chapter owner 对账（正文 ours 上下文的数须匹配 ours 值）
> - **L2 前移闭环**：Phase 5.6 全章草稿审计（auditor + cross_chapter）在正文未锁时跑，critical findings 触发 _quality_ensure rerun——解 FindingBus 死信箱
> - **L3 末轮机械**：引用真实性（cite key 全在 bib）+ 图-ref 一致（\ref 指向 \label）+ undefined ref warning

## v13.0 里程碑：内核重建 — 恢复 agent 设计初心

> **v13.0 核心突破**——系统性地治愈旧版的三大架构病灶：错误吞噬（42 处 `except Exception` 静默降级）、状态分裂（7 套不兼容 issue 结构 + 写读路径不一致）、上下文浪费（citation_context 每章重注 7 次）。方案是**收敛到少数契约**，而非新增更多模块。

### v13.0 内核契约层（`agent/core/`）

| 契约 | 文件 | 解决的旧病 |
|------|------|-----------|
| **错误分级** | `errors.py` | `TransientError`/`PermanentError`/`DegradedResult` + `classify()` 闸口；429 配额不再静默吞为"0图/0引用"；占位符不再进 PDF |
| **FactBase 单一事实源** | `factbase.py` | 替代 PaperContext 写读分裂；auditor/verifier/cross_chapter 读同一 `factbase.json`，消除数值分歧。**v15.3: as_fact_sheet 按 owner 分组（ours vs baseline），不再把 baseline 标 ours** |
| **分层记忆** | `memory.py` | `LayeredMemory` 三层（WORKING/EPISODIC/SEMANTIC）+ `get_or_compute()` 缓存重文本，消除 citation_context 7× 重算；`assemble(intent,budget)` 检索式组装 |
| **Finding 统一问题总线** | `finding.py` | `Finding`/`FindingBus` 统一 7 套 issue 结构；4 个适配器接入旧子系统；`as_revision_brief()` 回流到修订。**v15.3: Phase 5.6 前移让 findings 在草稿态被消费，不再死在后半程** |
| **QualityLoop 真闭环** | `quality_gate.py` + `loop._quality_ensure` | 章节修订不再只看 QualityGate 自身维度，同时修复 cross_chapter/auditor 发现的问题（一次修订修多类）。**v15.3: Phase 5.6 全章草稿审计触发 critical rerun** |
| **FigureManifest 文图联动** | `figure_manifest.py` | 图的结构化清单（替代裸字符串拼接）；确定性筛选（排除失败/占位/低质）；`validate_linkage()` 正文↔图对账 |

### v13.0 关键修复（对照旧版病灶）

| 旧版病灶 | v13.0 修复 |
|---------|-----------|
| ch5 f-string `\begin{X}` NameError → 2 词占位 | 错误分级：降级产物标记 `DegradedResult`，不进 PDF |
| figure_planner 遇 429 → 静默 0 图 | `classify()` 识别配额错误 + `results["figures_failed"]` 失败标记 |
| `getattr(dict,'project_path')` 永远 None | 改 `.get()` |
| 按计划数报告"生成完成 N 个"（实际全失败） | 按实际产出数 `_n_ok = snippets.count("\\begin{figure")` |
| citation_map UnboundLocalError → BibTeX 静默失败 | 预初始化 `citation_map = {}` + `bibtex_failed` 标记 |
| abstract/keywords 硬编码占位串 | DEGRADED 标记 + `*_failed` 标志 |
| `[To be generated]` stub 进 PDF | `DegradedResult`（`__bool__=False`，下游必识别） |
| Phase 0.5 失败仍标 completed | `_p0_5_ok` 判断 → 失败标 `partial` |
| PaperContext 写 checkpoint、验收器读 output | FactBase 保证双文件（`factbase.json` + 兼容 `paper_context.json`）都落盘 |
| `render_with_visual_review` 死 TODO（只记日志不重渲） | `_apply_defect_fixes()` 缺陷→修改规则表 + 真重渲闭环 |

### v13.0 架构原则（恢复四条初心）

| 初心 | v13.0 实现 |
|------|-----------|
| 代码=裁判 | 7 套 issue → 1 套 `Finding`；子系统通过 FindingBus 互读 |
| 零信任 | 错误分级：transient→重试 / permanent→失败标记 / 禁止"空值+completed" |
| 恒定上下文 | LayeredMemory 缓存 + `assemble(intent,budget)` 检索式组装 |
| THINK→EXECUTE→VERIFY→REFLECT 闭环 | FindingBus 简报回流到 `evaluate_and_revise` 修订 prompt |

### v13.0 验证（pipeline 实跑，96 分钟）

| 指标 | v12 旧版 | v13 新版 |
|------|---------|---------|
| Grade | A（虚高，含静默失败）| **B**（L1=100 L2=100 L3=50，诚实）|
| Traceback/致命错误 | 有（被吞）| **0** |
| 429 配额静默 | 3 次（吞为 0 图）| **0** |
| 图数 | 1（严重重叠）| **2**（架构图 7/10 + fig1 TikZ 自愈）|
| 跨章一致性误报 | 3（永久）| **0**（FactBase 生效）|
| 耗时 | ~150 分钟 | **96 分钟**（↓36%）|

### v13.0 保守清理（两轮，每个删除点 grep 验证 0 引用）

**第一轮（7 个死代码）**：`figure/{architecture_renderer,ablation_plotter,comparison_plotter,teaser_designer}.py`（4 个废弃渲染器）+ `test_batch1.py`/`test_v9_2.py`/`test_v9_3.py`（3 个废弃脚本）。

**第二轮（8 个废弃测试）**：`test_latex_direct.py`/`test_v9_1_figure_pgei.py`（2 个引用已删模块的坏测试）+ `test_v10_full.py`/`test_v10_llm_tikz.py`/`test_v10_quick.py`/`quick_pdf.py`/`test_quick_gen.py`/`test_quick_test.py`（6 个一次性 `__main__` 脚本，非 pytest）。

**保留原则**：核实为活依赖的不删——`figure/style_templates.py`（data_visualizer 3 处 import）、`figure/layout_engine.py`+`layout_templates.py`（测试引用）、`run_with_log.py`（文档化运行入口）。清理后 **263 个 pytest 测试 0 error**。

### v13.1 接线（P0 完成）：消掉"建了不接"的死接线

v13.0 内核接线率审计发现 6 块契约里 5 块仅 0-20% 接线（"徒增代码不涨性能"）。v13.1 不建新模块，**纯接线**：

| 接线项 | v13.0 状态 | v13.1 接通 |
|--------|-----------|-----------|
| **FindingBus 写入源** | 仅 cross_chapter 1 源 | ✅ +auditor +constraint +quality（4 类合并回流修订）|
| **FigureManifest 注入** | 0% 接线，裸字符串 | ✅ 实例化 + `_generate_figures` 录入 + `to_latex_snippets()` 输出 |
| **双重注入 bug** | 架构图注入两次 | ✅ 修复（remaining 派生排除架构图）|
| **文图对账** | 无 | ✅ `validate_linkage()` 正文↔图 label 对账 |

预期收益（待 pipeline 实跑验证）：修订简报从 1 类问题变 4 类合并；架构图不再重复；正文 \ref 有对账。

---

## v12.3 里程碑：架构净化 — PipelineContext + 依赖注入 + ch5 统一

> **v12.3 核心突破**——系统性消除三个架构级反模式：(1) 22 个散落的 `self._xxx` 状态变量 → 统一为 `PipelineContext` dataclass (2) `VenueAdapter` 全局可变状态（类级属性）→ 依赖注入参数链 (3) ch5 "架构孤儿" → 统一使用 ch1-4 共享基础设施。

### v12.3 架构改进

| 改进 | 之前 | 之后 |
|------|------|------|
| **PipelineContext** | loop.py 中 22 个 `self._xxx` 散落状态，58 次赋值，无统一契约 | `PipelineContext` dataclass 作为单一真相源，属性代理透明路由 |
| **VenueAdapter 依赖注入** | `build_style_instruction` 和 ch5 各自 `VenueAdapter()` 新建实例 → Phase 0.65 学习的风格丢失；v12.2 用类级属性修补（引入全局可变状态） | venue_adapter 通过参数链注入：`loop.py → run_chapterN → generate_* → build_style_instruction` |
| **ch5 架构统一** | ch5 不使用 `build_style_instruction`、不使用 `build_citation_instruction`、签名与其他章节不一致 | ch5 使用统一的 `build_style_instruction`，消除"架构孤儿" |

### v12.3 新增文件

| 文件 | 职责 |
|------|------|
| `agent/pipeline_context.py` | `PipelineContext` dataclass — 全局共享状态容器（17 个字段），支持 `to_checkpoint_dict()` / `from_checkpoint_dict()` / `save_to_checkpoint()` / `load_from_checkpoint()` |

### v12.3 回退 v12.2 的错误修复

| v12.2 错误修复 | 问题 | v12.3 正确方案 |
|------|------|------|
| VenueAdapter `_journal_style` / `_ref_style_guide` 改为**类级属性** | 引入全局可变状态，多线程/多论文场景下存在隐患 | 回退为实例属性 + 依赖注入参数链 |

### v12.2 CRITICAL 修复

| 问题 | 根因 | 影响 | 修复 |
|------|------|------|------|
| ch5 Conclusion 仅输出 2 词 | f-string `\begin{X}` 的 `{X}` 被解释为 Python 替换字段 → NameError → 异常被静默捕获 → 降级为 2 词 fallback | G4-S5 验收失败（chapter_words_5: 2 >= 500） | `\\begin{{X}}` 转义（与 ch1-ch4 对齐） |
| PaperContext 验收失败 | `_build_paper_context` 只更新内存不写磁盘 → `_read_paper_context_exists` 读磁盘返回 0 | G3-S6 失败 → CrossChapterChecker 无法修复数值矛盾 | 构建后持久化到 `paper_context.json` |
| 禁用术语永不修复 | `should_retry` 被分数判断覆盖：先设 True（有禁用术语），后被 `score < 70` 覆盖为 False | 论文禁用术语永远不会被修正 | 改为 `score_based OR issue_based` |
| 数值矛盾修复静默失效 | `_find_canonical_value` 的 `ours_values` 参数是死代码，只查 PaperContext | Abstract/章节间数值不一致无法自动修复 | 双路查找：PaperContext → ours_values 兜底 |

### v12.2 HIGH 修复

| 问题 | 修复 |
|------|------|
| VenueAdapter 实例断裂 → Phase 0.65 学习的风格丢失 | 依赖注入：`venue_adapter` 通过参数链传递（v12.3 修复，替代 v12.2 的类级属性方案） |
| ordered_gate `verify_all` 重复调用 2 次 | `run()` 中调用一次，传入两个 Gate |
| content_strategy/motivation_thread 未注入章节生成器（16 次 LLM 调用浪费） | `_run_chapter_phase` 注入到 `project_data` |

### Wave 1-6 架构重构

| Wave | 内容 |
|------|------|
| 1-5 | 删除 13 个废弃模块（~3,000 行死代码） |
| 6 | loop.py：`_CHAPTER_CONFIGS` 统一分发 + `_run_output_phase` 664→36 行 + 7 个子方法提取 |

---

## v12.0 里程碑：架构修正 — 通用性/特性分离 + 引用管线修复 + 事实表

> **v12.0 核心突破**——解决三个架构级问题：(1) 写作纪律通用层与期刊特性层分离 (2) 引用管线 join-then-split 消除 + citation 残留清理 (3) PaperContext 共享事实源解决跨章节数据矛盾。

### v12.0 核心改进

| 改进 | 说明 |
|------|------|
| **通用写作纪律层 (P0)** | `writing_discipline.md` 定义跨期刊的 10 条学术写作通用规则（信息密度/逻辑衔接/tone/禁用词/Oxford引用等），与 IEEE 特有规则分离 |
| **StyleManager 层级分离** | `_get_academic_rules()` 按优先级加载：P0(通用写作纪律) → P3(IEEE 词汇规则) → P5(清理规则) → 章节特定 → IEEE Trans 规则 |
| **引用管线消除 join-then-split** | `run_citation_manager_for_chapters()` 按 chapters dict 独立处理引用，全局统一编号，不再 join→split |
| **Phase 7.35 citation 残留清理** | tex 组装后兜底清理 `<citation>` 残留标记（Phase 7.3 LLM review 可能引入新标记） |
| **PaperContext 共享事实源** | 章节生成前从 project_data 提取硬件/epochs/loss/数据集/指标/模型名，注入每个 generator 的 prompt |
| **CrossChapterChecker 自动修复** | 基于 PaperContext 的数值矛盾自动修复，不再只报告不修复 |
| **中文字符正则过滤** | `_minimal_cleanup()` 自动过滤 LaTeX 中的中文字符残留 |

### v12.0 引用管线（修复后）

```
Phase 7.1: run_citation_manager_for_chapters(chapters dict)
            ├─ 按 chapter key 独立 collect <citation> 标记
            ├─ 汇总统一 verify + dedup（全局唯一编号）
            └─ 按 chapter key 独立 resolve → 更新 chapters dict
                    ↓
Phase 7.2: CrossChapterChecker.check_all(chapters, abstract)
            ├─ PaperContext 注入 → 数值矛盾自动修复
            └─ 返回 (issues, fixed_chapters)
                    ↓
Phase 7.3: LaTeX 组装 + LLM 审查
                    ↓
Phase 7.35: tex 后 citation 残留清理（正则兜底）
                    ↓
Phase 7.8: BibTeX [N] → \cite{key}
```

### v12.0 风格系统层级

```
StyleManager.build_chapter_style_instruction(chapter)
  ├─ P0: writing_discipline.md (跨期刊通用写作纪律, 10 条规则)
  ├─ P3: style_guide.md (IEEE 特有词汇规则/禁用词)
  ├─ P5: style_guide.md (清理规则)
  ├─ 章节特定规则 (hardcoded fallback)
  ├─ IEEE Trans 规则 (从 venue_profile)
  └─ 参考论文风格 (从 ref_pdf 学到的)
```

### v12.0 PaperContext 事实表

```
Phase 0.98: _build_paper_context()
  ├─ 从 project_data + experiment_design 提取
  │   hardware, training_params, loss_terms,
  │   datasets, metrics, model_name, innovation_names
  │
  ├─ 注入到 self._project_data["paper_context"]
  │   → 各 chapter generator 自动获得（通过 citation_context 参数）
  │
  └─ CrossChapterChecker 可据此修复数值矛盾
     例: Abstract "MAE=0.145" → PaperContext "MAE=0.133" → 自动修正
```

---

## v11.9 里程碑：Web Search API + LLM 提取验证

> **v11.9 核心突破**——集成智谱 Web Search API（`/paas/v4/web_search`）作为 MCP 配额耗尽后的独立备用通道；搜索结果通过 LLM 提取/验证为结构化学术论文信息，解决了"通用网页搜索 → 学术信息"的最后一公里问题。

### v11.9 核心改进

| 改进 | 说明 |
|------|------|
| **智谱 Web Search API 集成** | `POST /paas/v4/web_search`，Coding Plan key 兼容，独立配额（MCP 配额耗尽时仍可用） |
| **LLM 论文提取** | 搜索结果（博客/知乎/GitHub）→ LLM 识别并提取结构化学术论文（title/authors/year/venue/arxiv_id） |
| **LLM 引用验证** | 搜索结果 + 待验证标题 → LLM 判断是否匹配（verified + confidence + matched_url） |
| **BaseOrchestrator 单例** | LLM 提取/验证共用同一个 BaseOrchestrator 实例，避免重复模型列表扫描 |
| **缓存自动淘汰** | 搜索缓存超过 100 条时自动清理过期条目 |

### 搜索降级链 (v11.9)

```
search_papers():
  1. MCP web-search-prime   ← 主通道，质量好但有每周配额 (~0.3s)
  2. Web Search API + LLM   ← 独立配额，MCP 耗尽时接管 (~1.5s + LLM)
     ├─ Web Search API       返回 10-20 条网页结果
     ├─ LLM 提取             从网页中识别真实学术论文
     └─ 正则兜底             LLM 不可用时降级
  3. OpenAlex               ← 结构化学术数据，境内可达 (~10s)

verify_citation():
  1. MCP web-search-prime
  2. Web Search API + LLM   ← 独立配额，LLM 验证匹配度
  3. URL 域名匹配           ← LLM 未确认时低置信度兜底
  4. 百度学术
  5. Semantic Scholar

academic_search():
  1. 离线数据包 (32篇)
  2. Web Search API + LLM   ← 新增
  3. OpenAlex (300M+)
```

### Web Search API 流程图

```
           搜索请求 (query)
               │
     ┌─────────▼─────────┐
     │  Web Search API    │  POST /paas/v4/web_search
     │  ~1.5s, 返回10-20条 │  search_std (独立配额)
     └─────────┬─────────┘
               │
     ┌─────────▼─────────┐
     │  LLM 提取论文      │  BaseOrchestrator.call_light()
     │  ~0.5s, 结构化输出  │  "从网页中提取真实学术论文"
     └─────────┬─────────┘
               │
     ┌─────────▼─────────┐     互补
     │  OpenAlex 补全      │ ◄──────────────┐
     │  前3篇, 按相关性排序  │  语义理解好     │ 结构化好
     │  补: venue/DOI/     │  (WebSearch)   │ (OpenAlex)
     │  abstract/cites    │               │
     └─────────┬─────────┘     └──────────────┘
               │
        ┌──────┴──────┐
        │ 补全成功     │ 失败
        ▼             ▼
  source=ws+oa     source=ws
  完整结构化       仅LLM提取
```

### v11.8 Code Review 修复记录

| 问题 | 严重度 | 文件 | 修复 |
|------|--------|------|------|
| `quality_gate` style_score 默认 100 免费送分 | 🟡 High | `quality_gate.py` | 无 style checker 时 score=0，权重条件化 |
| `skip_task_by_name` 子串匹配误杀 | 🔴 Critical | `dispatcher.py` | `in` → `==` 精确匹配 |
| `auditor` Related Work must_contain 检测字面 "citation" | 🟡 High | `auditor.py` | 改用 regex patterns 匹配 `[N]`/`\cite{}`/方法动词 |
| `get_article_type_info()` 重复调用 | 🟢 Low | `quality_gate.py` | 合并为单次 try block |

### 模型降级链 (v11.9)

```
qwen3.7-max → glm-5.1 → tp_qwen3.7-max → qwen3.6-plus → tp_deepseek-v4-pro
→ glm-5 → tp_qwen3.6-plus → tp_deepseek-v4-flash → tp_qwen3.6-flash
→ glm-4.6v → glm-4.5v → claude-opus-4-7 → gpt-5.5
```

- GLM 系列全部走 `zai` SDK（ZhipuAIClient），原生支持 thinking 参数和 reasoning_content
- 视觉模型降级链：glm-4.6v → glm-4.5v → qwen3.6-plus(ali_token_plan) → qwen3.6-plus(ali_bailian)

---

## v11.7 里程碑：引用链路打通 + 境内网络自适应

> **v11.7 核心突破**——修复了 citation_bank 与章节生成器之间的架构断裂（LLM 现在能看到可用论文列表）；集成 OpenAlex 开源学术搜索（境内可达，300M+ 论文）；全面清理代码质量问题（38 处修复）；大幅优化运行耗时（4h → 2h）。

### v11.7 核心修复

| 修复 | 说明 |
|------|------|
| **citation_bank → 章节注入** | Phase 0.8 构建的 154 个 claim + 31 篇参考论文列表现在会注入每个章节的 LLM prompt，LLM 不再凭空编造引用 |
| **OpenAlex 学术搜索** | 新增 OpenAlex API（境内可达，~10s），覆盖 300M+ 论文。降级链：离线数据包 → MCP(智谱) → OpenAlex |
| **境内网络断舍离** | S2/CrossRef/DBLP/arXiv/DOIToBib 在境内全超时，已全部禁用。唯一外网通道：MCP 智谱 + OpenAlex |
| **离线验证模式** | `SKIP_ONLINE_VERIFICATION=1` 默认启用，Phase 6 参考文献审查不再逐个调 S2（省 80+ min） |
| **BibTeX metadata 模板** | 跳过 DOIToBib 在线获取（每个 DOI 100s 超时），直接用 metadata 模板生成（省 35 min） |
| **`[?]` 引用保留** | 未验证引用不再被删除，而是替换为最近有效编号，保留引用数量 |
| **表格通用动态模板** | Phase 7.95 从硬编码领域数据 → 通用动态模板（适配任意论文主题） |
| **38 处代码质量问题** | 27 处裸 `except` → 带日志；类型比较错误；随机引用改为最近编号；重复代码提取 |

### v11.7 运行效果

| 指标 | v11.4 | v11.5 | v11.6 | v11.7(预期) |
|------|-------|-------|-------|------------|
| Grade | C | C | C | **≥B** |
| L2 (内容完整度) | 83 | 66 | 83 | **≥85** |
| 运行耗时 | 255 min | 243 min | ~240 min | **~120 min** |
| BibTeX 条目 | 7 | 36 | 7 | **≥25** |
| 引用验证率 | 0/31 | — | 0/21 | **高(离线模式)** |
| citation_bank claims | 0 | 62 | 154 | **154+注入** |

### 参考文献获取架构 (v11.9)

```
                     检索请求
                        │
          ┌─────────────▼──────────────┐
          │  1. 离线数据包 (主路径)     │ ← data/reference_packs/*.json
          │     零网络依赖，境内可靠    │    32 篇预验证论文
          └─────────────┬──────────────┘
                        │ 数据不足
          ┌─────────────▼──────────────┐
          │  2. MCP web-search-prime    │ ← 智谱 MCP (境内代理)
          │     ~0.3s (有配额限制)      │    每周配额，用完降级
          └─────────────┬──────────────┘
                        │ 配额耗尽
          ┌─────────────▼──────────────┐
          │  3. Web Search API + LLM    │ ← /paas/v4/web_search (v11.9新增)
          │     ~1.5s + LLM提取         │    独立配额，网页→论文提取
          └─────────────┬──────────────┘
                        │ LLM 提取失败
          ┌─────────────▼──────────────┐
          │  4. OpenAlex               │ ← https://api.openalex.org
          │     ~10s, 300M+ 论文        │    开源免费，境内可达
          └────────────────────────────┘

  BibTeX: metadata 模板直接生成 (100% 成功, <1s/条)
```

### v11.7 引用链路（核心架构修复）

```
Phase 0.5a: 离线数据包(32篇) + OpenAlex → reference_pool.json (51+ 篇)
                    ↓
Phase 0.8:  build_citation_bank() → 154 claims (title+tags 技术描述)
                    ↓
_build_citation_context(): claims + 参考论文列表 → prompt 文本
                    ↓
Chapter 1-5: LLM 看到"可用论文列表" → 按论文标题匹配 <citation> 标记
                    ↓
Phase 7.1: 离线池匹配 + 全局兜底轮询 → 全部 <citation> → [N]
                    ↓
Phase 7.8: citation_map (25+) 条 → [N] → \cite{key}
                    ↓
Phase 7.95: 表格不足时动态补充通用模板
                    ↓
Phase 8: XeLaTeX 编译 → PDF
```

### 模型降级链 (v11.7)

```
qwen3.7-max → glm-5.1 → tp_qwen3.7-max → qwen3.6-plus → tp_deepseek-v4-pro
→ glm-5 → tp_qwen3.6-plus → tp_deepseek-v4-flash → tp_qwen3.6-flash
→ glm-4.6v → glm-4.5v → claude-3.7 → o3-mini
```

- GLM 系列全部走 `zai` SDK（ZhipuAIClient），原生支持 thinking 参数和 reasoning_content
- 视觉模型降级链：glm-4.6v → glm-4.5v → qwen3.6-plus(ali_token_plan) → qwen3.6-plus(ali_bailian)

### v11.7 Code Review 修复记录

| 问题 | 严重度 | 文件 | 修复 |
|------|--------|------|------|
| citation_bank 构建后从未传递给章节生成器 | 🔴 Critical | `loop.py` + `ch1~ch5` | 新增 `_build_citation_context()` + 5个章节注入 |
| 随机引用分配（学术诚信风险） | 🔴 Critical | `loop.py` | 改为最近有效编号 |
| `max(chapters.keys())` str/int 比较崩溃 | 🔴 Critical | `cross_chapter_checker.py` | `max(int(k)...)` |
| S2 验证在境内永远超时（白等 80+ min） | 🟡 High | `citation_manager.py` | 离线池≥20时跳过在线验证 |
| DOIToBib 5策略全超时（白等 35 min） | 🟡 High | `bibtex_builder.py` | 直接 metadata 模板 |
| Phase 7.15 删除 `[?]` 导致引用骤降 | 🟡 High | `loop.py` | 替换为最近编号而非删除 |
| Phase 7.95 硬编码 HCI 4D LF 数据 | 🟡 Medium | `loop.py` | 通用动态模板 |
| `_deduplicate_content` 段落顺序破坏 | 🟡 Medium | `loop.py` | 逐段原地判断保持顺序 |
| `_split_by_chapter_titles` 匹配过宽 | 🟡 Medium | `loop.py` | 要求 `#+` Markdown 标题行 |
| 27 处裸 `except` 无日志 | 🟡 Medium | agent/ 全目录 | 全部改为 `except Exception as e: logger.debug()` |
| 匿名类 `QReport` 重复构造 | 🟢 Low | `loop.py` | 提取为 `_complete_task()` 方法 |

---

## v11 里程碑：境内自适应 + 参考文献系统重构

> **v11 核心突破**——系统从"依赖国际学术API"进化为"离线数据包为主、在线API为辅"的境内友好架构；同时完成了 BibTeX 生成链重构、跨章节去重增强、统一API客户端升级等系统性改进。

### 核心能力

| 能力 | 说明 |
|------|------|
| **离线参考文献数据包** | 预构建验证过的论文 JSON 数据包（`data/reference_packs/`），零网络依赖，境内 100% 可用 |
| **OpenAlex 学术搜索** | 开源免费学术搜索 API，300M+ 论文，境内可达 (~10s) |
| **MCP 智谱代理** | web-search-prime + web-reader，境内唯一可靠外网通道 |
| **metadata BibTeX 模板** | 直接从论文元数据生成 BibTeX，100% 成功率，<1s/条 |
| **跨章节段落级去重** | 指纹级段落去重（85%重叠率阈值），保持原文顺序 |
| **统一 API 客户端** | `ZhipuAIClient`（zai SDK）+ `OpenAIClient` + `AnthropicClient` 三合一 |
| **执行-评价模型分离** | 跨 Provider 分离生成/评价模型，避免同源自我审查盲区 |
| **TCSVT 期刊完整配置** | 内容编排模式、论证节奏、审稿偏好、Red Flags 详细配置 |

---

## v10.1 里程碑：期刊自适应 + 内容策略驱动

> **v10.1 核心突破**——系统从"硬编码 IEEE TCSVT 风格"进化为"从参考论文自动学习任意期刊风格"，并在写作前规划内容策略。

### 核心能力

| 能力 | 说明 |
|------|------|
| **期刊风格自适应学习** | 从 ref_pdf/ 中的参考论文自动提取：内容组织模式、论证节奏、深度梯度、图表偏好 |
| **内容策略规划** | 每章写作前规划"写什么/不写什么/重点强调什么"（ContentStrategist） |
| **统一风格管理中心** | StyleManager 替代各章节独立的 `_build_style_instruction()`，7维度风格注入 |
| **分层文献搜索** | 5层递进搜索策略，由 RefSearchStrategist 驱动 |
| **LLM TikZ 示意图** | 数据/定性对比图无数据时，自动路由到 LLM 设计 TikZ 示意图 |

---

## v9.0 里程碑：首次完整论文输出

> **v9.0 标志性版本**——系统首次能够端到端生成一篇结构完整、编译无错、视觉可读的学术论文。

### 核心突破

| 能力 | 说明 |
|------|------|
| **LaTeX 直出生成** | 分章节直接输出 LaTeX 代码，不走 Markdown→LaTeX 中间转换 |
| **5层溢出自愈闭环** | 编译→检测 Overfull→自动修复→重编译→验证，0溢出0编译错误 |
| **完整论文输出** | 摘要 + 关键词 + 5章正文 + BibTeX参考文献，IEEE 格式 PDF |
| **章节级独立编译** | 每个子节独立生成+编译验证，失败则错误日志反馈 LLM 自愈 |

---

## 技术栈

- **Python 3.11+**: 主要开发语言（必须用 conda py311 环境）
- **多个 LLM API**: 智谱 GLM (zai SDK)、阿里云 Qwen、阿里 Token Plan、OpenAI、Claude
- **15级模型降级链**: qwen3.7-max → glm-5.1 → ... → o3-mini
- **学术搜索**: 离线数据包(32篇) → MCP 智谱 → Web Search API + LLM提取 → OpenAlex(300M+)
- **BibTeX**: metadata 模板直接生成（100% 成功）
- **LaTeX 编译**: XeLaTeX + bibtex，自动溢出检测与自愈
- **图表生成**: matplotlib + TikZ + pdflatex 编译验证

## 安装指南

### 1. 克隆项目
```bash
git clone <repository-url>
cd paper-writing-assistant
```

### 2. 创建 conda 环境
```bash
conda create -n py311 python=3.11
conda activate py311
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 配置 API 密钥
```bash
cp env.example .env
```

编辑 `.env` 文件：

| 环境变量 | 必需 | 说明 |
|---------|------|------|
| `GLM_CODING_PLAN_API_KEY` | **是** | 智谱 GLM（主力生成 + MCP 检索 + zai SDK） |
| `ALI_API_KEY` / `ALI_BAILIAN_API_KEY` | 推荐 | 阿里云百炼 Qwen（备选生成） |
| `ALI_TOKEN_PLAN_API_KEY` | 推荐 | 阿里 Token Plan（备选 provider） |
| `OPENAI_API_KEY` | 可选 | OpenAI O1/O3-mini（需代理） |
| `CLAUDE_API_KEY` | 可选 | Claude 3.7（需代理） |

> 境内网络环境：MCP 智谱 + OpenAlex 可用，S2/CrossRef/DBLP/arXiv 均超时。系统已自动适配。

## 使用方法

### 快速开始

1. **编辑配置** `config/project_config.py`（设置 `VENUE_TYPE`、`TARGET_VENUE`、`PAPER_TITLE`、`PROJECT_CODE_PATH`）
2. **放置项目代码** 到 `workspace/project_code/`
3. **放置参考 PDF**（可选）到 `ref_pdf/`
4. **运行**：
```bash
python pipeline.py              # 自动从断点恢复
python pipeline.py --no-resume  # 忽略检查点，从头开始
python pipeline.py --debug      # 调试模式
python pipeline.py --title "My Paper Title"    # 覆盖论文标题
```

### Pipeline 流程 (v12.2)

| Phase | 任务 | 说明 |
|-------|------|------|
| Phase 0 | 项目分析 | 分析工程代码 + 参考论文 |
| Phase 0.5a | **参考文献池** | 离线数据包(32篇) + OpenAlex 搜索 → 51+ 篇 |
| Phase 0.6-0.65 | **动机+风格** | 动机确认 + 期刊风格学习 + 内容策略规划 |
| Phase 0.8 | **引用支撑库** | 154 claims + 参考论文列表 → 注入章节 prompt |
| Phase 0.9 | **写作矩阵** | 写作理由矩阵（事前规划型） |
| Phase 0.95 | **消融实验** | 消融实验自动化 |
| Phase 0.98 | **PaperContext** | 构建共享事实源（硬件/epochs/loss/数据集/指标），v12.2 持久化到磁盘 |
| Phase 1-5 | **章节生成** | 逐章生成（v12.2: _CHAPTER_CONFIGS 统一分发 + content_strategy 注入 + PaperContext + 引用上下文） |
| Phase 6 | **文献审查** | 离线验证模式（跳过超时的 S2 在线验证） |
| Phase 7.1 | **引用解析** | 🆕 按 chapters dict 独立处理，无 join-then-split |
| Phase 7.2 | **跨章节检查** | 🆕 基于 PaperContext 数值矛盾自动修复 |
| Phase 7.3 | **LaTeX 组装** | 章节合并 → LLM 审查 → 模板填充 |
| Phase 7.35 | **citation 清理** | 🆕 tex 后 `<citation>` 残留清理（正则兜底） |
| Phase 7.8 | **BibTeX** | [N] → \cite{key} + BibTeX 条目生成 |
| Phase 8-9 | **编译+评价** | XeLaTeX 编译 → PDF 验证 → L1/L2/L3 评分 |

### 评分体系

```
Grade = L1×0.1 + L2×0.35 + L3×0.55
A ≥ 80, B ≥ 65, C ≥ 50, D < 50

L1: 代码可运行性 (满分100)
L2: 内容完整度 — 6项检查 (章节/字数/引用≥25/公式/表格≥3/无占位符)
L3: 学术质量 (LLM 评价)
```

### 输出

| 文件 | 说明 |
|------|------|
| `output/full_paper.pdf` | 最终 PDF 论文 |
| `output/latex/main.tex` | LaTeX 源码 |
| `output/latex/references.bib` | BibTeX 参考文献 (25+ 条) |
| `output/reference_pool.json` | 参考文献池 (51+ 篇) |
| `output/citation_bank.json` | 引用支撑库 (154 claims) |
| `output/citation_map.json` | [N] → \cite{key} 映射 |

## 项目结构

```
paper-writing-assistant/
├── agent/                        # 自主循环架构核心
│   ├── core/                     #   🆕 v13 内核契约层（6 块契约，零循环依赖）
│   │   ├── errors.py             #     错误分级 (Transient/Permanent/DegradedResult) + classify()
│   │   ├── factbase.py           #     FactBase 单一事实源（替代 PaperContext 写读分裂）
│   │   ├── memory.py             #     LayeredMemory 三层记忆 + citation_context 缓存
│   │   ├── finding.py            #     Finding 统一问题 + FindingBus + 4 适配器
│   │   └── figure_manifest.py    #     FigureManifest 文图联动单一真相源
│   ├── loop.py                   #   Pipeline 引擎 (v13: classify 闸口 + 8 处致命 except 分级)
│   ├── citation_manager.py       #   引用管理
│   ├── api_client.py             #   统一 API 客户端 (v13: classify 错误分级 + prompt 计数闸口)
│   ├── dispatcher.py             #   任务调度器
│   ├── quality_gate.py           #   质量门控 (v13: QualityLoop 接 FindingBus 简报)
│   ├── auditor.py                #   反幻觉审计
│   ├── cross_chapter_checker.py  #   跨章节一致性检查 (读 FactBase 权威数值)
│   ├── motivation_engine.py      #   动机确认引擎
│   ├── style_manager.py          #   统一风格管理 (P0 通用写作纪律层)
│   ├── hierarchical_planner.py   #   分层任务规划 (v13: 优先读 factbase.json)
│   ├── content_strategist.py     #   内容策略规划
│   └── skill_orchestrators/      #   章节编排器 (ch1-ch5 + reference_pool/checker)
├── api/
│   ├── openai_compatible.py      #   三合一统一客户端
│   ├── mcp_http_client.py        #   MCP StreamableHTTP 客户端
│   ├── web_search_api.py         #   智谱 Web Search API + LLM 提取
│   └── paper_search.py           #   MCP → Web Search API → OpenAlex 降级搜索
├── tools/
│   ├── academic_search.py        #   多源搜索 (offline + Web Search API + OpenAlex)
│   ├── bibtex_builder.py         #   BibTeX 构建
│   ├── latex_converter.py        #   LaTeX 组装 + 中文字符过滤
│   ├── arch_diagram_renderer.py  #   架构图渲染 (v13: 视觉评价真重渲闭环)
│   ├── figure_planner.py         #   图表规划
│   ├── figure_generator.py       #   TikZ 图表生成 (LLM 产规格 + 自愈编译)
│   ├── result_visualizer.py      #   实验结果可视化
│   ├── pdf_compiler.py           #   XeLaTeX 编译
│   ├── pdf_validator.py          #   PDF 验证 (Overfull/结构)
│   ├── latex_constraint_checker.py #  LaTeX 结构约束预审
│   ├── output_evaluator.py       #   L1/L2/L3 评价
│   └── reference_pack_manager.py #   离线数据包管理器
├── figure/                       #   图表模板 (v13 清理后仅保留活依赖)
│   ├── style_templates.py        #     期刊风格模板 (data_visualizer 依赖)
│   ├── layout_engine.py          #     TikZ 布局引擎
│   └── layout_templates.py       #     管道/分支模板
├── skills/
│   └── academic_writing_style/
│       ├── writing_discipline.md #   跨期刊通用写作纪律 (P0, 10条规则)
│       └── style_guide.md        #   IEEE 特有写作规范 (P3)
├── config/
│   ├── api_config.py             #   Provider 配置
│   ├── project_config.py         #   模型降级链 + 论文配置
│   └── venue_profiles/           #   期刊配置 (TCSVT/TIP/TPAMI/CVPR...)
├── test/                         #   pytest 测试 (v13 清理后 7 个有效模块，263 测试)
│   ├── conftest.py               #   pytest 配置
│   ├── test_systemic_upgrade.py  #   系统升级测试 (39)
│   ├── test_v10_1_smoke.py       #   冒烟测试 (26)
│   ├── test_citation_multisource.py # 引用多源测试 (24)
│   ├── test_v9_2_figure_system.py #  图表系统测试 (6)
│   ├── stage_targeted_test.py    #   分阶段测试 (4)
│   ├── test_pdf_validator.py     #   PDF 验证测试 (4)
│   └── test_phase85_quick.py     #   Phase 8.5 测试 (1)
├── data/
│   └── reference_packs/          #   离线参考文献
├── pipeline.py                   #   主入口
└── requirements.txt
```

## 扩展离线参考文献数据包

往 `data/reference_packs/` 中添加 JSON 文件即可扩展覆盖范围：

```json
{
  "domain": "your_research_domain",
  "description": "领域描述",
  "papers": [
    {
      "title": "论文标题",
      "authors": ["作者1", "作者2"],
      "year": 2024,
      "venue": "完整期刊/会议名",
      "venue_abbr": "简称",
      "doi": "10.xxxx/xxxxx",
      "abstract": "摘要（可选）",
      "citation_count": 100,
      "tags": ["关键词1", "关键词2"]
    }
  ]
}
```

## 免责声明

本工具仅用于学术研究与教育目的。使用者应确保：
- 遵守学术诚信与所在机构的行为规范
- 将输出内容用于写作学习、结构分析或内容规划参考
- 对生成内容进行必要的人工审查和个性化修改
- 承担使用本工具的全部责任
