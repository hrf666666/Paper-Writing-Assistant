# 安全审计报告

> **⚠️ 过时声明**：本报告基于 **v6.0（2026年4月）**，项目现已是 **v16.3**。
> 报告内引用的文件路径（`api/claude_37.py`、`tools/make_bibliography.py`、
> `utils/chapter2_utils.py`、`tools/tikz_generator.py` 等）大多已删除或重构：
> - API 客户端 → 统一到 `api/openai_compatible.py` + `mcp_http_client.py`
> - BibTeX → `tools/bibtex_builder.py` + `agent/core/citation_base.py`
> - 图表 → `tools/figure_generator.py` + `tools/arch_diagram_renderer.py`
> - 引用检查 → `agent/skill_orchestrators/reference_checker.py`
>
> 当前架构与模块清单以 `architecture.md`（§0.5 分层治理架构 + §12 目录结构）
> 和 `README.md` 为准。本报告保留作历史记录，**不再反映当前代码状态**。

## v6.0 安全改进（2026年4月）

### ✅ 代码注入漏洞修复

#### 1. 消除 `eval()` 调用
- **`skills/reference_checker.py`**: 两处 `eval()` 替换为 `ast.literal_eval()`
- **`tools/latex_converter.py`**: `eval()` 替换为 `ast.literal_eval()`
- **`tools/make_bibliography.py`**: `eval()` 替换为 `ast.literal_eval()`
- **`agent/api_client.py`**: 新增 `parse_json_response()` 安全 JSON 解析方法，替代直接 `eval()`

#### 2. 消除 `exec()` 调用
- **`utils/chapter2_utils.py`**: 删除了使用 `exec()` 执行文件内容的 `get_part_two_template()` 函数

#### 3. 模板渲染注入防护
- **`agent/skill_executor.py`**: `{{variable}}` 替换时清理替换值中的 `{{`/`}}` 标记，防止模板注入

### ✅ API 密钥安全

#### 1. 变量命名统一
- **`config/api_config.py`**: 所有 API Key 变量统一为 `UPPER_CASE` 命名风格，消除 `snake_case`/`UPPER_CASE`/混合大小写混用

#### 2. 无硬编码密钥
- 所有密钥仅从环境变量读取（`os.getenv("XXX", "")`），无硬编码回退值
- `env.example` 仅提供空键名模板，不含任何占位符值
- `.gitignore` 排除 `.env` 文件

#### 3. API Key 空值检查
- 所有 API 调用模块在发送请求前检查 Key 是否为空，提前报错而非静默失败

### ✅ SSL/TLS 安全

#### 1. 移除 SSL 验证禁用
- **`api/claude_37.py`**: 移除 `urllib3.disable_warnings()` 和 `verify=False`
- **`api/openai_o1.py`**: 同上
- **`api/openai_o3mini.py`**: 同上

### ✅ 资源管理

#### 1. HTTP 连接泄漏修复
- **`api/serper_normal.py`**: `HTTPSConnection` 在 `finally` 块中确保 `conn.close()`

#### 2. 原子文件写入
- **`agent/auditor.py`**: `save_reports()` 使用 `tempfile` + `os.replace` 原子写入，防止并发损坏

#### 3. 延迟初始化
- **`tools/ablation_designer.py`**, **`tools/result_visualizer.py`**, **`tools/tikz_generator.py`**: 模块级 `get_api_client()` 调用改为函数内延迟初始化

### ✅ 输入验证

#### 1. 人工指令长度限制
- **`agent/human_directive.py`**: `_parse_directives()` 添加 100KB 输入长度限制

#### 2. 检查点清理一致性
- **`agent/checkpoint.py`**: `clear()` 方法同时清理内存和磁盘文件

### ✅ 错误处理改进

#### 1. 移除静默异常吞没
- **`api/tavily_normal.py`**: `except Exception: pass` 改为 `logger.debug()` 记录
- **`api/serper_normal.py`**: 改进错误日志，记录每次重试的具体错误

#### 2. 统一日志系统
- 所有 API 模块从 `print()` 迁移到 `logging.getLogger(__name__)`

### ✅ 架构级安全改进

#### 1. 统一 API 客户端
- 所有 LLM API 调用通过 `UnifiedAPIClient` 统一入口
- 内置指数退避重试和模型降级机制

#### 2. MCP 独立客户端安全
- **`api/mcp_http_client.py`**: Session ID 自动管理，防止未授权调用
- API Key 在请求头中通过 HTTPS 传输

#### 3. 崩溃恢复
- `CheckpointManager` 确保每个阶段的状态持久化

#### 4. 人工监督
- `HumanDirective` 支持运行时人工干预（暂停/停止/跳过/重做/调整）

### ✅ 代码重复消除

- **`utils/chapter1_utils.py`**: 删除重复的 `extract_json_from_string()`，统一使用 `utils/json_utils`

## 安全检查结果

### 已验证无安全问题的内容
- ✅ 无 `eval()` 调用（已全部替换为 `ast.literal_eval()` 或安全 JSON 解析）
- ✅ 无 `exec()` 调用（已删除唯一的 `exec()` 使用）
- ✅ 无硬编码 API 密钥
- ✅ 无个人路径信息（已移除硬编码的 Windows 路径）
- ✅ 无内部网络配置
- ✅ 无 SSL 验证禁用
- ✅ 无 HTTP 连接泄漏
- ✅ 无静默异常吞没
- ✅ API 变量命名风格统一

### 保留的技术实现
- ✅ 核心算法逻辑
- ✅ 模型调用接口（统一通过 `UnifiedAPIClient`）
- ✅ MCP 增强检索（独立 HTTP 客户端 + IDE 注入双模式）
- ✅ 文档处理流程
- ✅ 质量控制机制

---

**审计更新时间**: 2026年4月
**审计版本**: v6.0
**审计状态**: ✅ 通过，可以开源
