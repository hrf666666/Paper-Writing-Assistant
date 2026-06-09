# 参考论文搜索策略引导 (Reference Paper Search Strategy Guide)

## 核心原则：精准收束，逐层放宽

参考论文的搜索不是"越全越好"，而是**围绕项目核心方向精准收束**。
优先找最相关的近 2 年论文，找不到再逐步放宽范围。

## 搜索策略层级（严格按顺序执行）

### Level 1: 核心创新方向（最精准）

从项目创新点中提取**2-3个核心技术关键词组合**，搜索近 2 年的论文。

**判断标准**：论文标题或摘要中同时包含核心方向的关键词。

**示例**：
- 项目核心：非朗伯体光场深度估计
- Level 1 搜索词：`"non-Lambertian light field depth estimation"`
- 年份范围：2024-2026
- 预期结果：5-15 篇

### Level 2: 核心方向 + 关键技术（精准扩展）

如果 Level 1 结果 < 5 篇，将核心方向与关键技术组合搜索。

**扩展策略**：
- 核心方向 + 每个创新点的关键技术
- 限制目标期刊/会议

**示例**：
- `"light field depth estimation" AND "material classification"` → 创新点1相关
- `"light field depth estimation" AND "dual-branch" OR "adaptive routing"` → 创新点2相关
- `"light field depth estimation" AND "cross-domain" AND "balanced training"` → 创新点3相关
- 年份范围：2023-2026

### Level 3: 核心子领域（领域扩展）

如果 Level 1+2 合计 < 10 篇，扩大到核心子领域。

**扩展规则**：
- 去掉最细粒度的限定词（如 "non-Lambertian"）
- 保留领域核心词（如 "light field depth estimation"）
- 年份范围扩展到 2021-2026

**示例**：
- `"light field depth estimation"` → 去掉 non-Lambertian 限定
- `"depth estimation" AND ("specular" OR "reflective" OR "transparent")` → 相关子领域

### Level 4: 大领域方向（兜底）

如果 Level 1-3 合计 < 15 篇，扩展到大领域。

**扩展规则**：
- 去掉子领域限定，只保留大方向
- 确保覆盖所有 baseline 方法
- **不含综述论文**（综述单独处理，见下方）

**示例**：
- `"depth estimation"` → 大领域
- `"light field" AND ("depth" OR "3D reconstruction")` → 光场相关

### Level 5: 综述论文（单独类别，特殊处理）

综述论文的组织结构、图片风格与研究论文完全不同，必须**单独划分**。

**何时搜索综述**：
- **总是**搜索 1-3 篇综述，但**仅用于 Related Work 章节的背景梳理**
- 综述**不参与** JournalStyleLearner 的风格学习（内容编排模式不同）
- 综述**不参与** figure_preferences 学习（综述图表多为分类汇总表，非架构图）

**搜索规则**：
- 搜索词：`"survey" OR "review" OR "taxonomy" OR "comprehensive review" + 领域词`
- 不限年份（综述的价值在于全面性，旧综述也可能有用）
- 目标数量：1-3 篇，不超过 3 篇
- 综述的 DOI 标记为 `is_survey: true`，供下游区分处理

**如果项目本身就是综述类论文**：
- 综述论文参与风格学习（此时综述风格就是目标风格）
- 需要下载更多综述（10+ 篇）作为风格参考

## 综述论文与研究论文的区分规则

| 判断条件 | 综述 | 研究论文 |
|----------|------|----------|
| 标题含 survey/review/taxonomy/benchmark/comprehensive | ✅ | ❌ |
| 摘要含 "we survey" / "we review" / "this paper presents a comprehensive" | ✅ | ❌ |
| 有明确的实验结果和消融 | ❌ | ✅ |
| 主体内容是对已有方法的分类和对比 | ✅ | ❌ |

**无法确定时**：默认归类为研究论文（宁可漏标综述，不可误标研究论文为综述）。

## 关键技术关键词提取规则

从项目创新点中提取搜索关键词时，遵循以下规则：

### 1. 英文化
- 中文学术概念必须转为英文学术标准术语
- 例："非朗伯体" → "non-Lambertian"
- 例："消融实验" → "ablation study"
- 例："光场" → "light field"

### 2. 组合规则
- 每个 Level 的搜索词 = `领域词 AND 技术词`
- 不要使用单个过宽的词（如只搜 "deep learning"）
- 使用引号包裹精确短语

### 3. 去重规则
- 同一篇论文不要重复下载
- 已在 ref_pdf/ 中的论文不要重复下载
- 用 DOI 作为唯一标识去重

## 搜索结果筛选标准

每篇搜索到的论文，需通过以下筛选：

| 维度 | 标准 | 权重 |
|------|------|------|
| 相关性 | 标题或摘要包含核心方向关键词 | 必须 |
| 时效性 | 近 2 年优先，经典论文不限 | 高 |
| 来源 | 目标期刊/会议的论文优先 | 高 |
| 引用量 | 高引用论文优先（经典论文） | 中 |
| 多样性 | 覆盖不同技术路线（每类至少 1 篇） | 中 |

## 目标数量

| 搜索层级 | 目标数量 | 累计目标 | 用途 |
|----------|----------|----------|------|
| Level 1 | 5-10 篇 | 5-10 | 核心参考 + 风格学习 |
| Level 2 | 5-10 篇 | 10-20 | 技术参考 + 风格学习 |
| Level 3 | 3-5 篇 | 13-25 | 背景参考 + 风格学习 |
| Level 4 | 3-5 篇 | 15-30 | 大领域参考 |
| Level 5 | 1-3 篇 | — | **仅 Related Work 背景梳理，不参与风格学习** |

**总计目标：15-30 篇研究论文 + 1-3 篇综述。**

如果某层级已经达到累计目标，**停止扩展**，不要盲目下载更多。

## 输出格式

LLM 搜索策略规划的输出格式：

```json
{
  "core_direction": "一句话描述项目核心研究方向",
  "is_survey_paper": false,
  "search_layers": [
    {
      "level": 1,
      "description": "核心创新方向搜索",
      "is_survey": false,
      "queries": [
        {"keywords": "exact search phrase", "year_from": 2024, "year_to": 2026, "venue": "target venue"},
        ...
      ],
      "target_count": 10,
      "stop_if_found": 5
    },
    {
      "level": 2,
      "description": "核心技术组合搜索",
      "is_survey": false,
      "queries": [...],
      "target_count": 10,
      "stop_if_found": 15
    },
    {
      "level": 3,
      "description": "子领域扩展",
      "is_survey": false,
      "queries": [...],
      "target_count": 5,
      "stop_if_found": 20
    },
    {
      "level": 4,
      "description": "大领域兜底",
      "is_survey": false,
      "queries": [...],
      "target_count": 5,
      "stop_if_found": 25
    },
    {
      "level": 5,
      "description": "综述论文（仅Related Work背景）",
      "is_survey": true,
      "queries": [
        {"keywords": "survey OR review + domain keyword", "year_from": 2020, "year_to": 2026, "venue": ""}
      ],
      "target_count": 3,
      "stop_if_found": 3
    }
  ],
  "must_include_dois": ["确保下载的关键论文DOI"],
  "excluded_keywords": ["排除的不相关关键词"]
}
```

## 反模式（必须避免）

1. **不要搜索过于宽泛的词**：如 "deep learning"、"computer vision"、"neural network"
2. **不要无限下载**：达到累计目标就停
3. **不要忽略目标期刊**：目标期刊的论文是学习风格的素材，必须包含
4. **不要只搜最新论文**：经典/综述论文对于 Related Work 是必要的
5. **不要搜到不相关领域的论文**：如做深度估计的不应该下载目标检测论文
