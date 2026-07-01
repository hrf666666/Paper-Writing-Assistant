# 论文范文写作助手 v17.0 (Paper Writing Assistant)

> **[English](README.en.md)** | 中文

一个基于多个大语言模型的智能顶刊论文范文写作系统。根据**文章类型 + 论文标题 + 项目实验工程代码**，自动生成完整的 5 章+摘要学术论文（LaTeX），作为写作参考或起点。

**v17.0 核心升级**：分层治理架构（审改验分离六层闭环）+ FactBase owner 三分类 + venue 驱动按章区分。采用 **THINK → EXECUTE → VERIFY → REFLECT** 自主循环架构。

---

## 它能做什么

| 能力 | 说明 |
|------|------|
| **端到端论文生成** | 从项目代码 + 参考论文 → 完整 5 章+摘要 IEEE 格式 PDF |
| **六层治理闭环** | 审（L1/L2）→ 改（L4a）→ 验（L4b）→ 仲裁（L3）→ 把关（L5），审改验分离 |
| **数值可信三道防线** | FactBase 真相注入 + 写后检测 + 带真相段落重写；owner 三分类防 baseline 被标 ours |
| **引用子系统治本** | cite 守恒守卫 + 单一真相源 inject，引用 100% 可追溯 |
| **边写边改闭环** | pipeline 从线性（生成→检测→报告）变成闭环（边写边改+全文检查） |
| **venue 自适应** | 11 个期刊/会议 profile（TCSVT/TIP/TPAMI/CVPR...），章节元素 venue 驱动 |
| **境内网络友好** | 离线数据包为主 + MCP 智谱 + OpenAlex，不依赖境内超时的国际学术 API |

---

## 核心架构：六层治理

针对 PDF 实跑暴露的"审了不改、改了不验、重复审无仲裁"问题，建立政府治理比喻的六层架构。

| 层 | 角色 | 模块 | 职责边界 |
|----|------|------|---------|
| **L1** | 省级 | `chapter_agent.py` ChapterAgent | 只管一章：生成→审→改→审计内聚；不碰别章 |
| **L2** | 部委（纵向专项） | `vertical_checkers.py` 5个Checker | 只审不改：bib/formula/table/figure/language |
| **L3** | 中央（全文协调） | `output_evaluator.py` GlobalReviewer | 全文视野仲裁：章节说好但全文差时，全文说了算 |
| **L4a** | 执行 | `fix_executor.py` FixExecutor | 只改不判：按 Finding 路由修复，确定性优先 |
| **L4b** | 纪检 | `verifier.py` ContentVerifier | 只验不改：改完复查通过才 resolve |
| **L5** | 决策中枢 | `loop.py` + `quality_gate.py` | 调度 + revise 后独立回归守卫 |

**核心原则**：审改验分离（三权不集中）、Finding 唯一载体、决策链单向、省级自治+中央仲裁。

> 详见 [architecture.md §0.5](architecture.md)

---

## 技术栈

- **Python 3.11+**（必须用 conda py311 环境）
- **LLM**：智谱 GLM 系列（glm-5.2/5.1/4.7/5/4.5v/4.6v，6 级降级链）
- **学术搜索**：离线数据包 → MCP 智谱 Web Search → OpenAlex（300M+ 论文）
- **BibTeX**：metadata 模板直接生成（100% 成功，<1s/条）
- **LaTeX 编译**：XeLaTeX + bibtex，溢出检测与自愈
- **图表**：matplotlib + TikZ + pdflatex 编译验证
- **PDF 验证**：PyMuPDF（fitz）结构+视觉检查

---

## 快速开始

### 1. 安装

```bash
git clone <repository-url>
cd paper-writing-assistant
conda create -n py311 python=3.11
conda activate py311
pip install -r requirements.txt
```

### 2. 配置

```bash
cp env.example .env
```

编辑 `.env`：

| 环境变量 | 必需 | 说明 |
|---------|------|------|
| `GLM_CODING_PLAN_API_KEY` | **是** | 智谱 GLM（主力生成 + MCP 检索 + zai SDK） |
| `ALI_TOKEN_PLAN_API_KEY` | 可选 | 阿里 Token Plan（备选 provider） |
| `ALI_BAILIAN_API_KEY` | 可选 | 阿里云百炼 Qwen（备选） |
| `OPENAI_API_KEY` | 可选 | OpenAI（需代理） |
| `CLAUDE_API_KEY` | 可选 | Claude（需代理） |

编辑 `config/project_config.py` 设置 `TARGET_VENUE`、`PAPER_TITLE`、`PROJECT_CODE_PATH`。

### 3. 运行

```bash
python pipeline.py              # 自动从断点恢复（默认）
python pipeline.py --no-resume  # 从头开始
python pipeline.py --debug      # 调试模式（DEBUG 日志）
python pipeline.py --title "My Paper Title"        # 覆盖标题
python pipeline.py --output ./my_output            # 覆盖输出目录
python pipeline.py --code-path /path/to/project    # 覆盖代码路径
```

> 境内网络：`SKIP_ONLINE_VERIFICATION=1` 默认开启，跳过超时的 S2/CrossRef/DBLP 在线验证。

---

## Pipeline 流程

| Phase | 任务 | 说明 |
|-------|------|------|
| **0.1-0.3** | 项目分析 | 分析工程代码 + 参考论文 PDF + 创新点验证 |
| **0.5** | 参考池+大纲 | 离线数据包 + OpenAlex → reference_pool（51+ 篇）+ 全局大纲 |
| **0.6-0.65** | 动机+风格 | 动机确认 + 期刊风格学习 + 内容策略规划 |
| **0.8** | 引用支撑库 | 154 claims → 注入章节 prompt |
| **0.95** | 消融实验 | 消融实验自动化（可选） |
| **0.98** | FactBase | 构建单一事实源（硬件/epochs/loss/数据集/指标），owner 三分类 |
| **0.99** | 图预规划 | 章节前文图联动规划 |
| **1-5** | **章节生成** | 🔄 走 ChapterAgent（L1 省级）：生成→质量闭环→子节校验→审计内聚 |
| **5.1-5.6** | 扩展+摘要 | Discussion/Limitations/摘要+关键词/前移审计 |
| **6-6.5** | 文献审查 | 参考文献审查 + cross_chapter 协调（6.5 已轻量化） |
| **7.x** | 输出组装 | 全局打磨→图表生成→LaTeX 组装→BibTeX→约束预检 |
| **8** | 编译 | PDF 编译（XeLaTeX）|
| **8.5** | PDF 验证 | 结构+视觉验证（max 3 轮修复） |
| **8.8** | 分层验收 | 原子级/抽象级/全局级验收 |
| **9** | **评价** | 🔄 L3 对抗式审稿（paperjury）+ L3 闭环重写 |

> **注**：Phase 0.7（exemplar_learner）/0.9（rationale_matrix）在 v14 已删，现为空转占位。

### 治理六层 → Phase 映射

| 治理层 | 跑在哪个 Phase |
|--------|---------------|
| L1 ChapterAgent | Phase 1-5 章节生成内（每章 run 全流程） |
| L2 纵向 Checker | Phase 8 编译前 + Phase 9 闭环后重跑 |
| L3 GlobalReviewer | Phase 9 评价 |
| L4a FixExecutor | Phase 8 编译前 + Phase 9 闭环后 |
| L4b Verifier | Phase 8（改完复查通过才 resolve） |
| L5 回归守卫 | Phase 1-5 revise 后 + Phase 9 重编译 |

---

## 评分体系

```
Grade = L1 × 0.10 + L2 × 0.35 + L3 × 0.55
A ≥ 80, B ≥ 65, C ≥ 50, D < 50

L1 格式有效性（满分100）：12 项检查（IEEE模板/无Markdown/无占位符/cite有效/...）
L2 内容完整度（满分100）：6 项检查（章节/字数/cite≥25/公式/表格≥3/无占位符）
L3 学术质量（满分100）：paperjury 对抗式审稿（两轮：Fatal-flaw + Forensic）

强制 D：critical_fails 存在 或 L1 < 60
critical_fails 每个 扣 L3 score 10 分
```

---

## 项目结构

```
paper-writing-assistant/
├── agent/                        # Agent 核心层
│   ├── core/                     #   内核契约层（5 块，零循环依赖）
│   │   ├── errors.py             #     错误分级 + classify()
│   │   ├── factbase.py           #     FactBase 单一事实源（owner 三分类）
│   │   ├── finding.py            #     Finding 统一问题 + FindingBus
│   │   ├── figure_manifest.py    #     FigureManifest 文图联动
│   │   └── citation_base.py      #     CitationBase 引用契约
│   ├── loop.py                   #   Pipeline 引擎（系统心脏）
│   ├── chapter_agent.py          #   🔄 L1 省级章节 agent（venue 驱动）
│   ├── auditor.py                #   反幻觉审计（L1 审计内聚）
│   ├── quality_gate.py           #   质量门控 + L5 回归守卫
│   ├── verifier.py               #   🔄 L4b 纪检验收
│   ├── fix_executor.py           #   🔄 L4a 执行机构
│   ├── cross_chapter_checker.py  #   跨章节一致性（读 FactBase）
│   ├── venue_adapter.py          #   期刊适配器
│   └── skill_orchestrators/      #   章节编排器
├── tools/
│   ├── vertical_checkers.py      #   🔄 L2 纵向 Checker（5 个专项）
│   ├── output_evaluator.py       #   🔄 L3 评价 + GlobalReviewer 仲裁
│   ├── latex_converter.py        #   LaTeX 组装
│   ├── figure_generator.py       #   TikZ 图表生成
│   ├── arch_diagram_renderer.py  #   架构图渲染
│   ├── pdf_compiler.py           #   XeLaTeX 编译
│   └── pdf_validator.py          #   PDF 验证
├── config/
│   ├── project_config.py         #   项目配置（标题/venue/模型链）
│   ├── api_config.py             #   Provider 配置
│   └── venue_profiles/           #   11 个期刊/会议 profile
├── api/                          # API 客户端层
├── test/                         # pytest 测试（92 + test_unit/ 449，均 gitignore）
├── pipeline.py                   # 主入口
└── requirements.txt
```

---

## 配置

### Venue Profiles（11 个）

| 类型 | 支持的 venue |
|------|-------------|
| 期刊 | IEEE TCSVT / TIP / TPAMI / IJCV / Pattern Recognition / Displays |
| 会议 | CVPR / ICCV / ECCV / AAAI / NeurIPS |

未命中时降级到 IEEE TIP。每个 profile 含章节预算/图表要求/内容编排模式/`chapter_elements`（venue 驱动按章区分）。

### 模型降级链（6 级，v15.3 连通性测试后仅保留实测可用的 GLM）

```
glm-5.2 → glm-5.1 → glm-4.7 → glm-5 → glm-4.5v → glm-4.6v
```

执行-评价模型分离（跨 provider 优先，避免同源自审盲区）。视觉模型：glm-4.6v → glm-4.5v。

---

## 输出文件

| 文件 | 说明 |
|------|------|
| `output/full_paper.pdf` | 最终 PDF 论文 |
| `output/latex/main.tex` | LaTeX 源码 |
| `output/latex/references.bib` | BibTeX 参考文献（25+ 条） |
| `output/factbase.json` | FactBase 事实库（owner 三分类） |
| `output/experiment_design.json` | 实验设计 |
| `output/figure_plan.json` | 图表规划 |
| `output/reference_pool.json` | 参考文献池（51+ 篇） |
| `output/citation_map.json` | [N] → \cite{key} 映射 |
| `output/chapterN/chapterN_*.md` | 各章 Markdown 草稿 |

---

## 扩展离线参考文献数据包

往 `data/reference_packs/` 中添加 JSON 文件即可扩展覆盖范围：

```json
{
  "domain": "your_research_domain",
  "papers": [
    {
      "title": "论文标题",
      "authors": ["作者1"],
      "year": 2024,
      "venue": "期刊/会议名",
      "doi": "10.xxxx/xxxxx",
      "tags": ["关键词"]
    }
  ]
}
```

---

## CHANGELOG

| 版本 | 关键变更 |
|------|---------|
| **v17.0** | 分层治理架构六层闭环（审改验分离）+ FactBase owner 三分类 + venue 驱动按章区分 + 死代码清理 + 文档双语文构 |
| v16.3 | 引用子系统治本（cite 守恒守卫）+ 数值校验正则降级 + resume 状态同步 |
| v16.2 | 边写边改 + 全文检查闭环（架构升级：线性→闭环） |
| v16.1 | 带真相的段落级重写（数值可信第三道防线） |
| v16 | 数值可信三道防线建立（真相注入+写后检测+重写） |
| v15.9 | FixAction executor + warning 可见化 |
| v15.8 | 弱点一致性闭环 + FactBase 对比结论 |
| v15.7 | 文图联动治本（规划前移 + 通信回路） |
| v15.6 | 实跑后深挖根因修复（4 个 bugfix） |
| v15.5 | 引用前置校验门 + figure plan 固化 |
| v15.3 | 评价可信化 + 数值 owner 真相源 + 前移闭环 |
| v14 | 内核契约层（errors/FactBase/Finding/FigureManifest/CitationBase）+ paperjury 对抗式审稿 |
| v13 | 内核重建（恢复 agent 设计初心）+ 接线消死接线 |
| v12 | 架构修正（通用性/特性分离）+ 引用管线修复 + 事实表 |
| v11 | 境内自适应 + 参考文献系统重构（离线包为主） |
| v10.1 | 期刊自适应 + 内容策略驱动 |
| v9.0 | 首次完整论文输出（LaTeX 直出 + 5层溢出自愈） |

> 详细架构演进见 [architecture.md](architecture.md) 附录。

---

## 免责声明

本工具仅用于学术研究与教育目的。使用者应确保：
- 遵守学术诚信与所在机构的行为规范
- 将输出内容用于写作学习、结构分析或内容规划参考
- 对生成内容进行充分的人工审查、修改与验证
- 如实标注所有引用来源，不伪造数据或结果

**作者不对因使用本工具而产生的任何学术不端行为承担责任。**
