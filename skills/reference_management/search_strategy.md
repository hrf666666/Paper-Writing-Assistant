# 学术文献搜索策略规则书 (v11.0)

> 本文件是 Phase 0.5 (reference_pool_builder) 的 LLM 搜索规则书。
> Python 只做管线编排和格式验证，所有搜索策略决策由 LLM 通过本规则引导。

## 1. 关键词提取规则

从项目数据提取搜索关键词时，遵循以下规则：

### 1.1 核心主题关键词
- 从 `innovation_points` 提取创新点名称和核心技术术语
- 每个创新点生成 1-2 个查询组，每组 2-4 个词
- **优先使用英文术语**，因为学术数据库以英文为主

### 1.2 方法关键词
- 从 `model_architecture` 提取模块名、架构名称
- 包含具体方法名（如 "transformer", "attention mechanism", "epipolar"）

### 1.3 数据集关键词
- 数据集名称本身就是极好的搜索关键词
- 配合具体任务类型（如 "HCI 4D light field dataset depth estimation"）

### 1.4 基线方法关键词
- 用基线方法名搜索其原始论文（如搜索 "EPINet" 找到 Heber2018）
- 搜索 "method_name + task" 找到相关改进论文

## 2. 搜索源优先级

```
1. Semantic Scholar — AI推荐相关论文，元数据完整，有引用数
   → 主力源，但有 429 限速风险
2. DBLP — 计算机科学专精，有直接 BibTeX endpoint
   → 补充源
3. CrossRef — 全学科覆盖，有 DOI + 引用数 + 期刊名
   → 网络条件好时启用
4. arXiv — 预印本，CS/物理/数学
   → 最新的未发表论文
```

## 3. 搜索结果筛选标准

按以下标准筛选搜索结果：

| 指标 | 阈值 | 说明 |
|------|------|------|
| 引用数 | > 10 | 优先选择高引用论文 |
| 发表年份 | 近 5 年优先 | 经典论文可放宽到 10 年 |
| 领域相关性 | 核心领域 > 相邻领域 > 交叉领域 | |
| 期刊/会议 | 顶会顶刊优先 | CVPR/ICCV/ECCV/TPAMI/TIP/TCSVT |

### 优先级排序
```
引用数 × 0.3 + 年份新近度 × 0.2 + 领域相关性 × 0.5
```

## 4. 降级规则

### 4.1 API 限速（429）
- S2 返回 429 → 自动切换到 DBLP/CrossRef
- 等待 60 秒后重试 S2
- 连续 3 次 429 → 标记该源冷却 5 分钟

### 4.2 搜索结果为空
- 放宽关键词（去掉最具体的修饰词）
- 使用同义词（如 "depth" → "3D reconstruction"）
- 去掉年份限制
- 去掉期刊限制

### 4.3 全部 API 不可用
- 使用本地缓存结果
- 使用 paper-fetch-skill 从 arXiv URL 获取
- 报错并停止，**不生成虚假引用**

## 5. 引用验证标准

**核心原则：绝不能信任 LLM 生成的引用信息，必须通过 API 验证。**

### 5.1 必须验证的字段
- DOI 必须可解析（通过 doi.org 或 CrossRef）
- 标题必须与搜索结果匹配（相似度 > 0.5）
- 作者 + 年份必须与搜索结果一致

### 5.2 验证失败处理
- 标记 `needs_verification = True`
- 不放入最终 BibTeX
- 在报告中列出需人工审核的条目

## 6. 禁止事项

1. **禁止编造 DOI** — LLM 生成的 DOI 100% 是假的
2. **禁止编造作者名** — "A. B. Smith" 式的假名
3. **禁止编造年份和期刊** — 必须来自搜索 API
4. **禁止混合不同论文的信息** — 不能把 A 论文的标题配 B 论文的 DOI
5. **禁止从记忆中"回忆"论文** — 必须通过搜索 API 实时查找

## 7. BibTeX 生成规则

### 7.1 优先路径
1. 从搜索结果中获取 DOI
2. 用 DOI Content Negotiation 直接获取标准 BibTeX
3. 无 DOI → CrossRef/S2/DBLP 元数据 → Python 模板组装
4. 全部失败 → 标记 needs_manual_review

### 7.2 格式规范
- entry type 根据会议/期刊自动判断
- cite key 格式: `firstauthor年份` 或 `keyword年份`
- 字段顺序: title → author → year → journal/booktitle → volume → pages → doi

### 7.3 特殊字符
- 标题中的 LaTeX 命令保留
- 作者用 `and` 连接
- 去掉 markdown 残留（`**`, `##` 等）
