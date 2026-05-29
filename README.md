# 论文范文写作助手 v9.0 (Paper Writing Assistant)

一个基于多个大语言模型的智能顶刊论文范文写作系统，采用 **THINK → EXECUTE → REFLECT** 自主循环架构，融合 **LaTeX 直出生成、5层溢出自愈闭环、动机驱动写作、深度范例学习、多代理审阅** 等先进机制，能够根据**文章类型 + 论文标题 + 项目实验工程代码**，自动生成完整的5章+摘要学术论文（LaTeX代码或Word文档），作为写作参考或起点。

## v9.0 里程碑：首次完整论文输出

> **v9.0 是一个标志性版本**——系统首次能够端到端生成一篇结构完整、编译无错、视觉可读的学术论文。

### 核心突破

| 能力 | 说明 |
|------|------|
| **LaTeX 直出生成** | 分章节直接输出 LaTeX 代码，不走 Markdown→LaTeX 中间转换，避免正则转换引入的错误 |
| **5层溢出自愈闭环** | 编译→检测 Overfull→自动修复→重编译→验证，0溢出0编译错误 |
| **完整论文输出** | 摘要 + 关键词 + 5章正文 + BibTeX参考文献，16页 IEEE 格式 PDF |
| **章节级独立编译** | 每个子节独立生成+编译验证，失败则错误日志反馈 LLM 自愈（最多2轮） |

### 5层溢出自愈链

```
LaTeX 源码
    │
    ├─ 1. _fix_textwidth_confusion   (textwidth→columnwidth 修正)
    ├─ 2. _ensure_table_resizebox    (补缺失的 resizebox)
    ├─ 3. _ensure_tikz_fits          (TikZ 包裹 resizebox)
    ├─ 4. _validate_float_sizing     (table*/figure* 降级)
    ├─ 5. _fix_long_equations        (超宽 equation→multline 拆行)
    │
    ▼ pdflatex 编译
    │
    ├─ 检测 Overfull \hbox/vbox
    ├─ 如有溢出→LLM 修复（1轮）→后处理链→重编译
    └─ 0溢出→通过 ✅
```

---

## v9.1 路线图：图表质量提升

> v9.0 实现了"能生成一篇能看的论文"，v9.1 将聚焦**生成图像的质量**，让主图达到目标期刊的审美水准。

通过 GLM-5V-turbo 视觉审阅，识别出以下 5 个核心问题：

### 问题诊断

| # | 问题 | 现状 | 目标 |
|---|------|------|------|
| 1 | **主图审美不达标** | 当前 TikZ/matplotlib 输出缺乏期刊级视觉设计 | 对标 IEEE TIP/TCSVT 等 top journal 主图风格 |
| 2 | **内容叠加影响观感** | 图层叠加无层次感，视觉混乱 | 引入 Z-order 管理 + 半透明分层 + 清晰视觉边界 |
| 3 | **详略不得当** | 主图试图包含所有细节，缺乏层次 | 主图抓主要矛盾，补充支图(fig. supplement)表现具体创新点 |
| 4 | **配色难看** | 默认 matplotlib/TikZ 配色不专业 | 引入学术级配色方案（参考 Nature/IEEE 审美） |
| 5 | **信息过载** | 要素太多无序堆砌，影响信息获取 | 内容有序组织，主次分明，引导读者视线流 |

### v9.1 改进方向

```
当前 v9.0 主图                    目标 v9.1 主图
┌─────────────────┐              ┌─────────────────┐
│  所有模块堆      │              │  主图: 清晰核心  │
│  在一起，无      │    ──→      │  架构+关键创新   │
│  层次感，配色    │              │  配色专业有序    │
│  默认难看        │              │                  │
└─────────────────┘              │  + 支图A: 模块X  │
                                 │  + 支图B: 模块Y  │
                                 │  + 支图C: 模块Z  │
                                 └─────────────────┘
```

---

## 历史版本演进

### v9.0 — LaTeX 直出 + 溢出自愈（当前）
- LaTeX 直出生成（`latex_direct_generator.py`）
- 5层溢出自愈闭环（0溢出0编译错误）
- 完整论文输出（摘要+关键词+5章+BibTeX）
- 章节级独立编译验证
- 有序门控流水线（P0格式→P1一致性→P2写作质量）

### v8.0 — 系统性架构升级
- VERIFY 独立验证层（8项纯代码检查，零LLM成本）
- 恒定大小上下文（3层记忆固定5000字符预算）
- 章节级状态机（outline→draft→review→revision→final）
- ToolTrace 反捏造（追踪工具调用，验证引用真实性）
- PDF 编译验证器（Phase 8.5）

### v7.0 — 动机驱动 + 实验驱动 + 多层审阅
- 合并 `auto_research_agent`、`PaperSpine`、`academic_paper_writer` 三个项目
- 动机确认与线程管理
- 6层深度范例学习
- 写作理由矩阵与闭卷重写
- 七锚测试 + 多代理独立审阅
- 消融实验自动化
- 期刊/会议模式自适应（Venue Profiles）
- 引用支撑库（Claim-Level Citation）

---

## 技术栈

- **Python 3.8+**: 主要开发语言
- **多个 LLM API**: 智谱 GLM (glm-5.1/glm-5)、阿里云 (qwen3.7-max/qwen3.6-plus)、阿里Token Plan (qwen3.7-max/deepseek-v4-pro)、OpenAI O1/O3-mini、Claude 3.7
- **11级模型降级链**: qwen3.7-max → glm-5.1 → tp_qwen3.7-max → qwen3.6-plus → tp_deepseek-v4-pro → glm-5 → tp_qwen3.6-plus → tp_deepseek-v4-flash → tp_qwen3.6-flash → claude-3.7 → o3-mini
- **LaTeX 编译**: pdflatex + bibtex，自动溢出检测与自愈
- **文档处理**: python-docx, PyMuPDF, markdown, BeautifulSoup
- **学术搜索**: Semantic Scholar API（免费）、MCP 增强检索、AMiner API
- **图表生成**: matplotlib + TikZ + pdflatex 编译验证
- **消融实验**: auto_research_agent 外部进程调用

## 安装指南

### 1. 克隆项目
```bash
git clone <repository-url>
cd Paper-Writing-Assistant
```

### 2. 创建虚拟环境
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 配置 API 密钥
```bash
cp env.example .env
```

编辑 `.env` 文件，填入您的 API 密钥：

| 环境变量 | 必需 | 说明 |
|---------|------|------|
| `GLM_CODING_PLAN_API_KEY` | **是** | 智谱 GLM（主力生成 + MCP 检索） |
| `ALI_API_KEY` / `ALI_BAILIAN_API_KEY` | 推荐 | 阿里云百炼 Qwen（备选生成） |
| `ALI_TOKEN_PLAN_API_KEY` | 推荐 | 阿里Token Plan（备选 provider） |
| `OPENAI_API_KEY` | 可选 | OpenAI O1/O3-mini（需代理） |
| `CLAUDE_API_KEY` | 可选 | Claude 3.7（需代理） |
| `AMINER_API_KEY` | 可选 | AMiner 学术搜索 |

> Semantic Scholar API 免费，无需 Key。

## 使用方法

### 快速开始

1. **编辑配置文件** `config/project_config.py`
   - 设置 `VENUE_TYPE`（`journal` / `conference`）
   - 设置 `TARGET_VENUE`（`TIP` / `CSVT` / `TPAMI` / `CVPR` / `NeurIPS` 等）
   - 设置 `PAPER_TITLE`
   - 设置 `PROJECT_CODE_PATH`（项目实验代码路径）
2. **放置项目代码** 到 `workspace/project_code/`
3. **放置参考 PDF**（可选）到 `ref_pdf/`
4. **运行**：
```bash
python pipeline.py              # 自动从断点恢复
python pipeline.py --no-resume  # 忽略检查点，从头开始
python pipeline.py --debug      # 调试模式
python pipeline.py --title "My Paper Title"    # 覆盖论文标题
python pipeline.py --output ./my_output         # 覆盖输出目录
python pipeline.py --code-path ./my_project     # 覆盖代码路径
```

5. **动机确认**（v7.0+）：pipeline 会在 Phase 0.5 暂停，等待用户确认动机方案
6. **人工干预**（运行时可选）：编辑 `output/HUMAN_DIRECTIVE.md`

### 配置选项

| 配置项 | 说明 | 默认值 |
|-------|------|--------|
| `VENUE_TYPE` | 期刊(`journal`)或会议(`conference`) | `journal` |
| `TARGET_VENUE` | 目标投稿期刊/会议 | `TIP` |
| `ENABLE_AUDIT` | 启用反幻觉审计 | `True` |
| `RUN_ABLATION` | 运行消融实验（需 auto_research_agent） | `False` |
| `CHECK_REFERENCES` | 验证引用真实性 | `True` |
| `OUTPUT_LATEX` | 输出 LaTeX（否则输出 Word） | `True` |
| `API_CALL_INTERVAL` | API 调用间隔（秒） | `3.0` |

### 模型配置

在 `config/project_config.py` 中按优先级配置模型列表：

```python
# 生成模型优先级（国内优先）
GENERATION_MODELS = [
    "glm_5_1",        # 智谱GLM-5.1
    "qwen3_6_plus",   # 阿里云百炼 Qwen3.6-Plus
    "claude_37",      # Claude 3.7 Sonnet（需代理）
]

# 推理/决策模型
REASONING_MODELS = ["glm_5_1", "qwq_32b", "o1"]

# 轻量模型（分类/判断）
LIGHT_MODELS = ["glm_4_flash", "qwen_plus"]
```

### Pipeline 流程（v9.0）

| Phase | 任务 | 说明 |
|-------|------|------|
| Phase 0 | 项目分析 | 分析工程代码 + 参考论文 PDF |
| **Phase 0.5** | **研究与范例学习** | **动机确认 + 引用支撑库 + 范例学习档案** |
| Phase 1-5 | 章节生成 | 逐章生成（动机线程驱动 + 写作理由矩阵），质量门控自动迭代 |
| Phase 5.5 | 摘要生成 | 基于所有章节内容生成 Abstract & Keywords |
| **Phase 5.6** | **消融实验自动化** | **调用 auto_research_agent 执行真实消融 → 结果收集 → 图表生成** |
| Phase 6 | 参考文献审查 | 验证引用真实性和可检索性 |
| Phase 6.5 | 反幻觉审计 | 全论文审计 + 七锚测试 + 多代理审阅 |
| **Phase 7** | **LaTeX 直出** | **分章节直接生成 LaTeX + 5层溢出自愈 + BibTeX 编译** |
| **Phase 8.5** | **PDF 验证** | **编译验证 + 结构检查 + 引用完整性 + 自动修复** |

### Pipeline 架构图

```
pipeline.py 主入口
    │
    ├─ Phase 0: 项目分析
    │
    ├─ Phase 0.5: 研究与范例学习
    │   ├─ 动机确认子流程 → confirmed_motivation.md
    │   ├─ 引用支撑库构建 → citation_support_bank.md
    │   └─ 范例学习档案 → exemplar_dossier.md + style_profile.md
    │
    ├─ Phase 1-5: 章节生成
    │   └─ 动机线程 + 写作理由矩阵 + 闭卷重写
    │
    ├─ Phase 5.5-5.6: 摘要 + 消融实验
    │   ├─ auto_research_agent 子进程
    │   ├─ 结果收集与验证
    │   └─ 图表自动生成（三线表 + 柱状图/雷达图）
    │
    ├─ Phase 6-6.5: 质量保证
    │   ├─ 七锚测试
    │   ├─ 多代理独立审阅
    │   ├─ 反幻觉审计
    │   └─ 跨章节一致性检查
    │
    ├─ Phase 7: LaTeX 直出 (v9.0)
    │   ├─ 分章节直接生成 LaTeX（不走 Markdown 中间格式）
    │   ├─ 5层溢出自愈闭环
    │   └─ BibTeX 参考文献编译
    │
    └─ Phase 8.5: PDF 验证
        ├─ 编译验证 + Overfull 检测
        ├─ PDF 结构检查（页数/元素）
        └─ 引用完整性验证
```

### 文献检索架构

```
                     检索请求
                        │
              ┌─────────▼──────────┐
              │  MCP HTTP 客户端    │ ← GLM_CODING_PLAN_API_KEY
              │  (web-search-prime) │
              └─────────┬──────────┘
                        │ 失败/不可用
              ┌─────────▼──────────┐
              │  Semantic Scholar   │ ← 免费，无需 Key
              └─────────┬──────────┘
                        │ 超时/失败
              ┌─────────▼──────────┐
              │    AMiner API      │ ← AMINER_API_KEY
              └────────────────────┘
```

### 输出

| 目录/文件 | 说明 |
|----------|------|
| `output/latex_direct/` | **v9.0 LaTeX 直出生成输出（分章节）** |
| `output/quick_test/` | **v9.0 编译验证输出（完整 PDF）** |
| `output/latex/main.tex` | LaTeX 论文（模板填充） |
| `output/full_paper.md` | Markdown 版本 |
| `output/chapter1-5/` | 各章节独立文件 |
| `output/abstract/` | 摘要文件 |
| `output/confirmed_motivation.md` | 确认后的动机方案 |
| `output/exemplar_dossier.md` | 范例学习档案 |
| `output/style_profile.md` | 写作风格画像 |
| `output/citation_support_bank.md` | 引用支撑库 |
| `output/rationale_matrix.json` | 写作理由矩阵 |
| `output/seven_anchor_report.json` | 七锚测试报告 |
| `output/multi_review_report.json` | 多代理审阅报告 |
| `output/reference_pool.json` | 参考文献池 |
| `output/outline.json` | 全局大纲 |
| `output/ablation_results/` | 消融实验结果（真实数据） |
| `output/figures/` | 图表输出（teaser/architecture/comparison/ablation） |
| `output/checkpoints/` | 检查点文件（用于崩溃恢复） |

## 项目结构

```
Paper-Writing-Assistant/
├── agent/                        # 自主循环架构核心
│   ├── loop.py                   #   自主循环引擎（6子流程阶段路由）
│   ├── api_client.py             #   统一 API 客户端（配置驱动）
│   ├── memory.py                 #   双层记忆系统（动机线程存储）
│   ├── checkpoint.py             #   检查点管理（崩溃恢复）
│   ├── quality_gate.py           #   质量门控（5维评估+场景适配）
│   ├── human_directive.py        #   人工指令系统
│   ├── dispatcher.py             #   任务调度器（Leader-Worker 模式）
│   ├── auditor.py                #   反幻觉审计引擎（七锚测试+浅层编辑检测）
│   ├── citation_manager.py       #   统一引用管理器
│   ├── cross_chapter_checker.py  #   跨章节一致性检查器
│   ├── skill_executor.py         #   Skill 执行引擎
│   ├── skill_registry.py         #   Skill 注册与发现
│   ├── motivation_engine.py      #   动机确认与线程管理引擎
│   ├── exemplar_learner.py       #   6层深度范例学习引擎
│   ├── rationale_matrix.py       #   写作理由矩阵生成器
│   ├── closed_book_rewriter.py   #   闭卷重写模块
│   ├── seven_anchor_test.py      #   七锚测试引擎
│   ├── multi_reviewer.py         #   多代理独立审阅协调器
│   ├── venue_adapter.py          #   期刊/会议场景适配器
│   └── skill_orchestrators/      #   多步编排器（各章节）
├── ablation/                     # 消融实验自动化
│   ├── orchestrator.py           #   消融编排器
│   ├── result_collector.py       #   实验结果收集与验证
│   └── table_generator.py        #   LaTeX/Markdown 消融表格生成
├── figure/                       # 核心主图设计
│   ├── teaser_designer.py        #   Teaser figure 设计与生成
│   ├── architecture_renderer.py  #   架构图高级渲染（TikZ+pdflatex验证）
│   ├── comparison_plotter.py     #   SOTA 对比图专业绘制
│   ├── ablation_plotter.py       #   消融实验结果可视化
│   └── style_templates.py        #   图表风格模板库
├── api/                          # 各模型 API 调用模块
│   ├── openai_compatible.py      #   统一 OpenAI 兼容客户端
│   ├── mcp_http_client.py        #   MCP StreamableHTTP 独立客户端
│   └── paper_search.py           #   Semantic Scholar + MCP 增强检索
├── config/
│   ├── api_config.py             #   Provider 配置 + 模型别名映射 + 降级链
│   ├── project_config.py         #   项目配置 + VENUE_TYPE/TARGET_VENUE
│   └── venue_profiles/           #   期刊/会议场景配置（11个）
│       ├── base_profile.py       #   场景基类
│       ├── journal_tip.py        #   IEEE TIP
│       ├── journal_csvt.py       #   IEEE TCSVT
│       ├── journal_tpami.py      #   IEEE TPAMI
│       ├── conf_cvpr.py          #   CVPR
│       └── conf_neurips.py       #   NeurIPS
├── skills/                       # Skill 目录（YAML 配置 + prompt 模板）
├── tools/
│   ├── latex_direct_generator.py # ★ v9.0 LaTeX 直出生成器 + 5层溢出自愈
│   ├── latex_converter.py        #   Markdown → LaTeX 转换（备选）
│   ├── tikz_generator.py         #   TikZ 架构图生成
│   ├── bibtex_builder.py         #   BibTeX 参考文献构建
│   ├── pdf_validator.py          #   Phase 8.5 PDF 编译验证器
│   ├── output_evaluator.py       #   输出有效性 + 完整度评价
│   └── figure_generator.py       #   论文图表生成器
├── utils/                        # 工具函数
├── ref_pdf/                      # 参考 PDF 存放目录
├── workspace/                    # 项目工程代码存放目录
├── test/                         # 单元测试 + 集成测试
├── pipeline.py                   # 主入口（v9.0）
├── requirements.txt              # 依赖清单
└── env.example                   # 环境变量示例
```

## 各章节 Skill 核心任务

| 章节 | 核心任务 |
|------|---------|
| **Ch.1 Introduction** | 动机线程锚点 → 强调问题重要性和难度 → 指出现有方法不足 → 介绍本文方法与贡献 |
| **Ch.2 Related Work** | 分类综述，引用密度均匀，不足指向本项目（会议模式可压缩为1段） |
| **Ch.3 Methodology** | 总体架构+架构图（创新点高亮）→ 各模块详解（公式+架构+功能）→ 损失函数 |
| **Ch.4 Experiments** | 数据集描述 → SOTA性能对比 → 消融实验（真实数据+三线表+图表） |
| **Ch.5 Conclusion** | 凝练贡献+局限性+未来工作（期刊模式可扩展 Discussion 章节） |
| **Abstract** | 问题→局限→方法→结果→贡献，自包含，150-250词 |

## 配置说明

### Venue 配置

| Venue | 类型 | LaTeX模板 | 最大页数 | 消融数 | 摘要字数 | Tier |
|-------|------|----------|---------|--------|---------|------|
| IEEE TIP | journal | IEEEtran | 14 | 5-8 | 250 | top_journal |
| IEEE TCSVT | journal | IEEEtran | 14 | 5-8 | 250 | top_journal |
| IEEE TPAMI | journal | IEEEtran | 14 | 6-10 | 250 | top_journal |
| CVPR | conference | CVPR | 8 | 2-3 | 200 | top_conference |
| NeurIPS | conference | NeurIPS | 10 | 2-3 | 200 | top_conference |

### 期刊 vs 会议差异

| 维度 | 期刊模式 | 会议模式 |
|------|---------|---------|
| Discussion 章节 | 独立章节（扩展） | 融入 Conclusion |
| Limitation 章节 | 独立章节 | 融入 Conclusion |
| Related Work | 完整分类综述 | 压缩为1-2段 |
| 消融实验 | 5-8 个 | 2-3 个 |
| 数据集 | 3-5 个 | 2-3 个 |
| Computational Analysis | 需要 | 可选 |

## 依赖清单

| 分类 | 包名 | 说明 |
|------|------|------|
| 核心 API | `openai`, `requests`, `python-dotenv`, `tavily-python` | LLM 调用 + 网络请求 |
| 数据格式 | `PyYAML` | Skill 配置解析 |
| 进度条 | `tqdm` | 章节生成进度 |
| Markdown→Word | `markdown`, `beautifulsoup4`, `python-docx`, `latex2mathml`, `mathml2omml`, `lxml` | Word 输出 |
| 可视化 | `matplotlib`, `numpy` | 图表生成 |
| PDF 解析 | `PyMuPDF` | 参考 PDF 读取 |
| LaTeX 编译 | `pdflatex`（系统） | TikZ 架构图编译验证 |

## 免责声明

本工具仅用于学术研究与教育目的。使用者应确保：
- 遵守学术诚信与所在机构的行为规范
- 将输出内容用于写作学习、结构分析或内容规划参考
- 对生成内容进行必要的人工审查和个性化修改
- 承担使用本工具的全部责任
