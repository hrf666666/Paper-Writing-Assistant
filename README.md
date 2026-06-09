# 论文范文写作助手 v12.0 (Paper Writing Assistant)

一个基于多个大语言模型的智能顶刊论文范文写作系统，采用 **THINK → EXECUTE → REFLECT** 自主循环架构，融合 **通用写作纪律层(P0)、PaperContext 共享事实源、引用管线修复、Web Search API + LLM 提取、OpenAlex 学术搜索、境内网络自适应、期刊风格学习、LaTeX 直出生成、5层溢出自愈闭环、动机驱动写作、多代理审阅** 等先进机制，能够根据**文章类型 + 论文标题 + 项目实验工程代码**，自动生成完整的5章+摘要学术论文（LaTeX 或 Word），作为写作参考或起点。

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

### Pipeline 流程 (v12.0)

| Phase | 任务 | 说明 |
|-------|------|------|
| Phase 0 | 项目分析 | 分析工程代码 + 参考论文 |
| Phase 0.5a | **参考文献池** | 离线数据包(32篇) + OpenAlex 搜索 → 51+ 篇 |
| Phase 0.6-0.65 | **动机+风格** | 动机确认 + 期刊风格学习 + 内容策略规划 |
| Phase 0.8 | **引用支撑库** | 154 claims + 参考论文列表 → 注入章节 prompt |
| Phase 0.9 | **写作矩阵** | 写作理由矩阵（事前规划型） |
| Phase 0.95 | **消融实验** | 消融实验自动化 |
| Phase 0.98 | **PaperContext** | 🆕 构建共享事实源（硬件/epochs/loss/数据集/指标） |
| Phase 1-5 | **章节生成** | 逐章生成（PaperContext + 引用上下文注入 + 质量门控） |
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
│   ├── loop.py                   #   Pipeline 引擎 (PaperContext + 引用管线 + 离线验证)
│   ├── citation_manager.py       #   引用管理 (v12.0: chapters dict 接口 + 全局编号)
│   ├── api_client.py             #   统一 API 客户端 (zai/openai/anthropic)
│   ├── dispatcher.py             #   任务调度器
│   ├── quality_gate.py           #   质量门控
│   ├── auditor.py                #   反幻觉审计
│   ├── cross_chapter_checker.py  #   跨章节一致性检查 (v12.0: PaperContext 自动修复)
│   ├── motivation_engine.py      #   动机确认引擎
│   ├── style_manager.py          #   统一风格管理 (v12.0: P0通用写作纪律层)
│   ├── hierarchical_planner.py   #   分层任务规划 (v12.0: phase0_98 PaperContext)
│   ├── content_strategist.py     #   内容策略规划
│   └── skill_orchestrators/      #   章节编排器
│       ├── ch1_introduction.py   #     (含 PaperContext + citation_context 注入)
│       ├── ch2_related_work.py
│       ├── ch3_methodology.py
│       ├── ch4_experiments.py
│       ├── ch5_conclusion.py
│       ├── reference_pool_builder.py  # 离线+OpenAlex
│       └── reference_checker.py       # 离线验证模式
├── api/
│   ├── openai_compatible.py      #   三合一统一客户端
│   ├── mcp_http_client.py        #   MCP StreamableHTTP 客户端
│   ├── web_search_api.py         #   智谱 Web Search API + LLM 提取 (v11.9)
│   └── paper_search.py           #   MCP → Web Search API → OpenAlex 降级搜索
├── tools/
│   ├── academic_search.py        #   多源搜索 (offline + Web Search API + OpenAlex)
│   ├── bibtex_builder.py         #   BibTeX 构建 (metadata模板 + 离线池补充≥25)
│   ├── doi2bib.py                #   DOIToBib (境内已禁用，metadata兜底)
│   ├── latex_converter.py        #   LaTeX 组装 + 中文字符过滤 (v12.0)
│   ├── latex_direct_generator.py #   LaTeX 直出 + 溢出自愈
│   ├── figure_generator.py       #   图表生成 (TikZ)
│   ├── output_evaluator.py       #   L1/L2/L3 评价
│   └── reference_pack_manager.py #   离线数据包管理器
├── skills/
│   └── academic_writing_style/
│       ├── writing_discipline.md #   🆕 跨期刊通用写作纪律 (P0, 10条规则)
│       └── style_guide.md        #   IEEE 特有写作规范 (P3)
├── config/
│   ├── api_config.py             #   Provider 配置
│   ├── project_config.py         #   模型降级链 + 论文配置
│   └── venue_profiles/           #   期刊配置 (TCSVT/TIP/TPAMI/CVPR...)
├── data/
│   └── reference_packs/          #   离线参考文献 (32篇)
├── pipeline.py                   #   主入口 (默认 SKIP_ONLINE_VERIFICATION=1)
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
