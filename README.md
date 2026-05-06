# 论文范文写作助手 v6.0 (Paper Writing Assistant)

一个基于多个大语言模型的智能顶刊论文范文写作系统，采用 **THINK → EXECUTE → REFLECT** 自主循环架构，能够根据**文章类型 + 论文标题 + 项目实验工程代码**，自动生成完整的5章+摘要学术论文（LaTeX代码或Word文档），作为写作参考或起点。

## v6.0 核心升级（相比 v5.0）

### 1. 配置驱动 API 体系
- **统一 OpenAI 兼容接口**：智谱 GLM、阿里云百炼、OpenAI、Claude 全部走同一调用路径
- **模型自动降级**：按优先级列表自动切换，国内 API 优先，国际 API 备选
- **启动时健康检查**：自动检测 API Key 可用性，过滤不可用的 Provider
- **模型别名映射**：`api_config.PROVIDERS` 配置驱动，新增模型只需改配置

### 2. 参考文献池（Anti-Fabrication）
- **Phase 0.5 新增**：写作前通过 Semantic Scholar + LLM 关键词扩展批量检索真实论文
- **按主题/方法/数据集/基线**分类构建搜索查询
- **引用来源锁定**：LLM 只能从已验证的真实论文池中选择引用，杜绝编造
- **去重 + 相关度排序**：按引用数排序，截取 Top-N

### 3. 全局大纲规划器
- **Content Checklist**：每章定义必须覆盖的内容项（如 Introduction 需包含 3-4 条贡献）
- **篇幅预算**：每章 min/max/target 词数约束
- **子节推导**：基于项目数据自动推导 Methodology 子节标题
- **禁用术语注入**：大纲中嵌入论文等级约束

### 4. 统一引用管理器
- **完整工作流**：collect → verify → dedup → resolve → format_bibliography
- **双通道验证**：优先从预构建的 reference_pool 匹配，回退到在线检索
- **`<citation>` → `[n]`**：自动替换所有引用标记为标准数字引用格式
- **未验证标记**：无法验证的引用标记为 `[?]`，需人工检查

### 5. 跨章节一致性检查器
- **5 项一致性检查**：
  - 术语一致性：同一概念在不同章节的表达
  - 数值一致性：Abstract 中的数字与 Experiments 对比
  - 章节引用一致性：Introduction 提到的 Section N 是否存在
  - 格式一致性：全文 Markdown/LaTeX 不混用
  - 引用编号连续性：`[1]-[N]` 无跳号

### 6. MCP 增强文献检索
- **智谱 MCP 三服务集成**：web-search-prime（网络搜索）+ web-reader（网页读取）+ zread（GitHub 文档搜索）
- **独立 HTTP 客户端**：通过 `GLM_CODING_PLAN_API_KEY` 直接调用，无需 IDE 环境
- **三级检索优先级**：MCP → Semantic Scholar → AMiner
- **深度验证**：`deep_verify_reference()` 结合 MCP + 语义搜索进行最严格验证

## 技术栈

- **Python 3.8+**: 主要开发语言
- **多个 LLM API**: 智谱 GLM (glm-5.1/glm-4-plus)、阿里云百炼 (qwen3.6-plus/qwq-32b)、OpenAI O1/O3-mini、Claude 3.7
- **文档处理**: python-docx, PyMuPDF, markdown, BeautifulSoup
- **学术搜索**: Semantic Scholar API（免费）, 智谱 MCP 增强检索, AMiner API（可选）
- **MCP 服务**: 智谱 GLM Coding Plan（web-search-prime, web-reader, zread）
- **LaTeX 生成**: TikZ 架构图自动生成
- **可视化**: matplotlib（消融实验图表）
- **公式转换**: latex2mathml, mathml2omml（Word 公式支持）

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
| `ZHIPU_GLM_API_KEY` | **是** | 智谱 GLM 大模型（主力生成） |
| `GLM_CODING_PLAN_API_KEY` | 推荐 | MCP 增强检索（web-search-prime/web-reader/zread） |
| `ALI_BAILIAN_API_KEY` | 推荐 | 阿里云百炼 Qwen（备选生成） |
| `OPENAI_API_KEY` | 可选 | OpenAI O1/O3-mini（需代理） |
| `CLAUDE_API_KEY` | 可选 | Claude 3.7（需代理） |
| `AMINER_API_KEY` | 可选 | AMiner 学术搜索 |
| `SERPER_API_KEY` | 可选 | Serper 网页抓取 |
| `TAVILY_API_KEY` | 可选 | Tavily 搜索 |

> Semantic Scholar API 免费，无需 Key。

## 使用方法

### 快速开始

1. **编辑配置文件** `config/project_config.py`
   - 设置 `ARTICLE_TYPE`（IEEE Trans / ACM Top Conf / CCF A / CCF B）
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

5. **人工干预**（运行时可选）：编辑 `output/HUMAN_DIRECTIVE.md`

### 配置选项

| 配置项 | 说明 | 默认值 |
|-------|------|--------|
| `ENABLE_AUDIT` | 启用反幻觉审计 | `True` |
| `RUN_ABLATION` | 运行消融实验设计 | `False` |
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

### Pipeline 流程

| Phase | 任务 | 说明 |
|-------|------|------|
| Phase 0 | 项目分析 | 分析工程代码 + 参考论文 PDF |
| **Phase 0.5** | **参考文献池 + 大纲** | **批量检索真实论文 + 生成全局大纲（v6.0 新增）** |
| Phase 1-5 | 章节生成 | 逐章生成，质量门控自动迭代，每章后即时审计 |
| Phase 5.5 | 摘要生成 | 基于所有章节内容生成 Abstract & Keywords |
| Phase 6 | 参考文献审查 | 验证引用真实性和可检索性 |
| Phase 6.5 | 反幻觉审计 | 全论文审计：步骤验证、引用反向检索、内容真实性校验 |
| Phase 7 | 输出 | **引用解析 → 跨章节一致性检查 → LaTeX/Word/Markdown 输出** |

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

- **MCP 优先**：通过 `GLM_CODING_PLAN_API_KEY` 调用智谱 MCP 服务，支持网络搜索和网页读取
- **自动降级**：MCP 不可用时自动回退到 Semantic Scholar，再到 AMiner
- **双模式**：支持独立 HTTP 调用（生产环境）和 IDE 注入模块（开发环境）

### 输出

| 目录/文件 | 说明 |
|----------|------|
| `output/latex/main.tex` | LaTeX 论文 |
| `output/full_paper.md` | Markdown 版本 |
| `output/chapter1-5/` | 各章节独立文件 |
| `output/abstract/` | 摘要文件 |
| `output/chapter3/architecture_figure.tex` | TikZ 架构图 |
| `output/reference_pool.json` | **v6.0 参考文献池** |
| `output/outline.json` | **v6.0 全局大纲** |
| `output/references.md` | **v6.0 格式化参考文献列表** |
| `output/cross_chapter_check.json` | **v6.0 跨章节一致性报告** |
| `output/audit_detail.json` | 详细审计报告 |
| `output/audit_summary.json` | 审计汇总报告 |
| `output/ablation_design.json` | 消融实验设计方案 |
| `output/code_analysis.json` | 代码结构分析结果 |
| `workspace/ablation_test/` | 消融实验代码/图表输出 |
| `output/checkpoints/` | 检查点文件（用于崩溃恢复） |
| `output/memory_state.json` | 记忆系统状态 |

## 项目结构

```
Paper-Writing-Assistant/
├── agent/                        # ★ 自主循环架构核心
│   ├── loop.py                   #   自主循环引擎（含引用解析+一致性检查）
│   ├── api_client.py             #   统一 API 客户端（v2.0 配置驱动）
│   ├── memory.py                 #   双层记忆系统
│   ├── checkpoint.py             #   检查点管理（崩溃恢复）
│   ├── quality_gate.py           #   质量门控（4维评估+禁用术语+自动重试）
│   ├── human_directive.py        #   人工指令系统（PAUSE/RESUME/SKIP/REDO）
│   ├── dispatcher.py             #   任务调度器（Leader-Worker 模式）
│   ├── auditor.py                #   反幻觉审计引擎（v5.0）
│   ├── citation_manager.py       # ★ v6.0 统一引用管理器
│   ├── cross_chapter_checker.py  # ★ v6.0 跨章节一致性检查器
│   ├── skill_executor.py         #   Skill 执行引擎（自动注入 tier+风格）
│   └── skill_registry.py         #   Skill 注册与发现（YAML 配置驱动）
├── api/                          # 各模型 API 调用模块
│   ├── openai_compatible.py      # ★ v6.0 统一 OpenAI 兼容客户端
│   ├── mcp_http_client.py        # ★ v6.1 MCP StreamableHTTP 独立客户端
│   ├── paper_search.py           #   Semantic Scholar + MCP 增强检索
│   └── *.py                      #   旧接口兼容层
├── config/
│   ├── api_config.py             # ★ v6.0 Provider 配置 + 模型别名映射
│   └── project_config.py         #   项目输入配置 + 论文等级约束 + 模型优先级
├── skills/                       # Skill 目录（YAML 配置 + prompt 模板）
│   ├── chapter1_introduction/    #   第1章 Introduction
│   ├── chapter2_related_work/    #   第2章 Related Work
│   ├── chapter3_methodology/     #   第3章 Methodology
│   ├── chapter4_experiments/     #   第4章 Experiments
│   ├── chapter5_conclusion/      #   第5章 Conclusion
│   ├── abstract/                 #   摘要和关键词
│   ├── ablation_design/          #   消融实验设计
│   ├── citation_strategy/        #   引用策略规划
│   ├── detail_gradient/          #   细节梯度控制
│   ├── experiment_designer/      #   实验设计器
│   ├── length_budget/            #   篇幅预算
│   ├── project_analyzer/         #   项目代码分析
│   ├── workload_decomposer/      #   工作负载分解
│   ├── reference_pool_builder.py # ★ v6.0 参考文献池构建器
│   ├── structure_planner.py      # ★ v6.0 全局大纲规划器
│   ├── reference_checker.py      #   参考文献审查
│   └── content_reviewer.py       #   内容审查
├── tools/
│   ├── latex_converter.py        #   Markdown → LaTeX（特殊字符保护）
│   ├── tikz_generator.py         #   TikZ 架构图生成
│   ├── markdown2docx_converter.py#   Markdown → Word（公式转换）
│   ├── ablation_designer.py      #   消融实验设计器（v5.0）
│   ├── ablation_runner.py        #   消融实验运行器
│   └── result_visualizer.py      #   结果可视化工具
├── utils/                        # 工具函数
├── ref_pdf/                      # 参考 PDF 存放目录
├── workspace/
│   ├── project_code/             #   项目工程代码存放目录
│   └── ablation_test/            #   消融实验代码/图表输出
├── pipeline.py                   # ★ 主入口（v6.0）
├── requirements.txt              # ★ 依赖清单
└── env.example                   # 环境变量示例
```

## 各章节 Skill 核心任务

| 章节 | 核心任务 |
|------|---------|
| **Ch.1 Introduction** | 强调问题重要性和难度 → 指出现有方法不足 → 介绍本文方法与贡献 |
| **Ch.2 Related Work** | 分类综述，引用密度均匀，不足指向本项目 |
| **Ch.3 Methodology** | 总体架构描述+TikZ图（创新点高亮）→ 各模块详解（公式+架构+功能）→ 损失函数 |
| **Ch.4 Experiments** | 数据集描述 → SOTA性能对比 → 消融实验设计 |
| **Ch.5 Conclusion** | 凝练贡献+局限性+未来工作 |
| **Abstract** | 问题→局限→方法→结果→贡献，自包含，150-250词 |

### 审查 & 审计 Skills

| Skill | 功能 |
|-------|------|
| **auditor** | 反幻觉审计（步骤验证、引用反向检索、内容真实性校验） |
| **quality_gate** | 4维评估（学术规范/逻辑连贯/引用自然/内容完整）+ 禁用术语检测 + 自动迭代修改 |
| **reference_checker** | 验证引用可检索性、出处真实性（Semantic Scholar + MCP） |
| **content_reviewer** | 句式清晰度、文风学术性、逻辑连贯性（多轮审查→修改→再审查） |
| **citation_manager** | v6.0 引用管理（收集→验证→去重→编号→替换） |
| **cross_chapter_checker** | v6.0 跨章节一致性（术语/数值/格式/引用编号） |
| **reference_pool_builder** | v6.0 参考文献池构建（批量检索+去重+排序） |
| **structure_planner** | v6.0 全局大纲规划（Checklist+篇幅预算+子节推导） |

## 消融实验使用指南

### 启用消融实验

在 `config/project_config.py` 中设置：
```python
RUN_ABLATION = True
```

### 完整流程

1. **设计阶段**（自动执行）：
   - 分析项目代码结构（模型模块、数据加载、训练流程）
   - 从 ref_pdf 学习消融实验设计模式
   - 生成消融实验方案 JSON（含目标模块、修改方式、预期结果）
   - 生成可执行的消融实验 Python 脚本

2. **运行阶段**（手动执行）：
   ```bash
   cd workspace/ablation_test/code
   python run_all_ablations.py
   ```

3. **可视化阶段**（自动执行）：
   - 读取实验结果数据
   - 生成对比图表（柱状图、雷达图、瀑布图）
   - 生成 LaTeX/Markdown 表格

## 配置说明

### 文章类型支持

| 类型 | LaTeX模板 | 最大页数 | 摘要字数 | Tier |
|------|----------|---------|---------|------|
| IEEE Trans | IEEEtran | 14 | 250 | top_journal |
| ACM Top Conf | acmart | 12 | 200 | top_conference |
| CCF A | IEEEtran | 14 | 250 | top_venue |
| CCF B | IEEEtran | 12 | 200 | good_venue |

### Tier 约束示例

| 禁用术语 | 推荐替换 |
|---------|---------|
| curriculum learning | progressive training / multi-stage training / staged training |
| student-teacher | knowledge distillation (模型压缩) / guided training (训练策略) |
| pedagogical | （避免使用） |

## 依赖清单

| 分类 | 包名 | 说明 |
|------|------|------|
| 核心 API | `openai`, `requests`, `python-dotenv`, `tavily-python` | LLM 调用 + 网络请求 |
| 数据格式 | `PyYAML` | Skill 配置解析 |
| 进度条 | `tqdm` | 章节生成进度 |
| Markdown→Word | `markdown`, `beautifulsoup4`, `python-docx`, `latex2mathml`, `mathml2omml`, `lxml` | Word 输出 |
| 可视化 | `matplotlib`, `numpy` | 消融实验图表（可选） |
| PDF 解析 | `PyMuPDF` | 参考 PDF 读取（可选，可换 `pdfplumber`/`PyPDF2`） |

## 免责声明

本工具仅用于学术研究与教育目的。使用者应确保：
- 遵守学术诚信与所在机构的行为规范
- 将输出内容用于写作学习、结构分析或内容规划参考
- 对生成内容进行必要的人工审查和个性化修改
- 承担使用本工具的全部责任
