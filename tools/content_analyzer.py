# -*- coding: utf-8 -*-
"""
Tool: 内容分析器 v9.2 (Content Analyzer)

从论文 LaTeX 全文中提取：
1. 叙事结构（问题→动机→方法→验证）
2. 核心创新点（名称+描述+视觉提示）
3. 每张图表的信息传达目标

这是图表规划的前置步骤，解决"图表与论文内容脱节"的根本问题。

依赖: api/openai_compatible.py (LLM 调用)
"""

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── 数据结构 ──

@dataclass
class InnovationPoint:
    """论文创新点"""
    name: str                          # 短名称 (≤5词)
    description: str                   # 一句话描述
    visual_hint: str = ""              # 如何在图表中视觉化展示
    importance: int = 1                # 1=核心, 2=重要, 3=辅助
    related_modules: List[str] = field(default_factory=list)  # 关联模块ID


@dataclass
class FigureNeed:
    """单张图表的信息传达需求"""
    purpose: str                       # 这张图要传达什么信息
    target_audience: str = "reviewer"  # reviewer / reader
    must_show: List[str] = field(default_factory=list)  # 必须展示的元素
    key_message: str = ""              # 一句话核心信息（给审稿人的takeaway）
    suggested_layout: str = ""         # 推荐布局: pipeline/dual_branch/pyramid/encoder_decoder/parallel/recursive
    suggested_fig_type: str = ""       # teaser/module_detail/ablation/comparison/qualitative
    priority: int = 1                  # 1=必须, 2=推荐, 3=可选


@dataclass
class ContentBrief:
    """论文内容凝练摘要，驱动图表规划"""
    core_contribution: str = ""        # 一句话核心贡献
    method_name: str = ""              # 方法简称
    narrative_flow: List[str] = field(default_factory=list)  # 叙事流
    innovation_points: List[InnovationPoint] = field(default_factory=list)
    figure_needs: List[FigureNeed] = field(default_factory=list)
    key_modules: List[Dict] = field(default_factory=list)  # 核心模块 [{id, label, role}]
    raw_sections: Dict[str, str] = field(default_factory=dict)  # 原始章节文本


# ── LLM 分析 Prompt ──

_ANALYZE_SYSTEM_PROMPT = """You are an expert academic paper analyst specializing in IEEE TCSVT/TIP journals.
Your task is to deeply analyze a paper's content and extract the information needed to plan effective figures.

Key principles:
1. Figures in top journals serve a PURPOSE — they communicate the paper's core contribution visually.
2. Every figure should have a clear "one-glance message" that a reviewer can understand in 5 seconds.
3. The main architecture figure (teaser) should capture the ENTIRE method in one view.
4. Innovation points must be visually prominent in the figures.

Output MUST be valid JSON. No markdown, no explanation outside JSON."""

_ANALYZE_USER_PROMPT = """Analyze this paper deeply and extract figure-relevant information.

## Paper Title
{title}

## Abstract
{abstract}

## Introduction
{intro_text}

## Methodology
{method_text}

## Experiments (if available)
{experiment_text}

## Output Format (JSON)
Return a JSON object with this EXACT structure:
{{
  "core_contribution": "One sentence: what is the main contribution of this paper?",
  "method_name": "Short name of the proposed method (≤5 words)",
  "narrative_flow": [
    "Problem: ...",
    "Motivation: ...",
    "Approach: ...",
    "Validation: ..."
  ],
  "innovation_points": [
    {{
      "name": "Short name (≤5 words)",
      "description": "One sentence description",
      "visual_hint": "How to visually represent this in a figure",
      "importance": 1,
      "related_modules": ["m1", "m2"]
    }}
  ],
  "figure_needs": [
    {{
      "purpose": "What information this figure should communicate",
      "target_audience": "reviewer",
      "must_show": ["element1", "element2"],
      "key_message": "The one-glance takeaway for reviewers",
      "suggested_layout": "pipeline",
      "suggested_fig_type": "teaser",
      "priority": 1
    }}
  ],
  "key_modules": [
    {{"id": "m1", "label": "Module Name", "role": "input|processing|core|output|fusion"}}
  ]
}}

Rules:
- Innovation importance: 1=core contribution, 2=important component, 3=auxiliary technique
- suggested_layout must be one of: pipeline, dual_branch, pyramid, encoder_decoder, parallel, recursive
- suggested_fig_type must be one of: teaser, module_detail, ablation, comparison, qualitative
- For a typical journal paper, plan 3-5 figures:
  * 1 teaser (main architecture)
  * 1-2 module_detail (innovation details)
  * 1 comparison (SOTA comparison)
  * 1 ablation (component ablation)
- must_show should list specific elements that MUST appear in the figure
- key_message should be what a reviewer understands from the figure in 5 seconds
- key_modules should list ALL major components of the method pipeline
- priority: 1=must have, 2=strongly recommended, 3=optional
"""


def analyze_paper_content(
    paper_content: Dict,
    model_alias: str = "glm_5_2",
) -> ContentBrief:
    """
    深度分析论文内容，提取图表所需信息。

    Args:
        paper_content: dict with keys: title, abstract, intro_text, method_text, experiment_text
        model_alias: LLM 模型别名

    Returns:
        ContentBrief 对象
    """
    from api.openai_compatible import query_model

    # 尝试 LLM 分析
    prompt = _ANALYZE_USER_PROMPT.format(
        title=paper_content.get("title", "Untitled"),
        abstract=paper_content.get("abstract", "")[:2000],
        intro_text=paper_content.get("intro_text", "")[:3000],
        method_text=paper_content.get("method_text", "")[:4000],
        experiment_text=paper_content.get("experiment_text", "")[:2000],
    )

    logger.info("[ContentAnalyzer] 调用 LLM 分析论文内容...")
    brief = None

    for alias in [model_alias, "qwen3_7_max", "tp_qwen3_7_max", "glm_5"]:
        try:
            raw = query_model(prompt, alias, system_prompt=_ANALYZE_SYSTEM_PROMPT,
                              temperature=0.3, max_tokens=4096)
            parsed = _parse_json_response(raw)
            if parsed:
                brief = _dict_to_brief(parsed)
                logger.info(f"[ContentAnalyzer] {alias} 分析成功")
                break
        except Exception as e:
            logger.warning(f"[ContentAnalyzer] {alias} 失败: {e}")
            continue

    if brief is None:
        logger.warning("[ContentAnalyzer] 所有 LLM 失败，使用规则提取")
        brief = _rule_based_analysis(paper_content)

    # 补全和验证
    brief = _validate_brief(brief, paper_content)

    logger.info(
        f"[ContentAnalyzer] 分析完成: "
        f"贡献={brief.core_contribution[:50]}..., "
        f"创新点={len(brief.innovation_points)}, "
        f"图表需求={len(brief.figure_needs)}"
    )
    return brief


def analyze_from_tex(tex_path: str, model_alias: str = "glm_5_2") -> ContentBrief:
    """从 LaTeX 文件分析论文内容"""
    paper_content = _extract_from_tex(tex_path)
    return analyze_paper_content(paper_content, model_alias)


# ═══════════════════════════════════════════════════════════════
# LaTeX 解析
# ═══════════════════════════════════════════════════════════════

def _extract_from_tex(tex_path: str) -> Dict:
    """从 LaTeX 文件提取结构化内容"""
    with open(tex_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取标题
    title_match = re.search(r'\\title\{(.+?)\}', content, re.DOTALL)
    title = _clean_latex(title_match.group(1)) if title_match else "Untitled"

    # 提取摘要
    abs_match = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', content, re.DOTALL)
    abstract = _clean_latex(abs_match.group(1)) if abs_match else ""

    # 提取各章节
    sections = _extract_sections(content)

    return {
        "title": title,
        "abstract": abstract,
        "intro_text": sections.get("introduction", ""),
        "method_text": sections.get("methodology",
                                     sections.get("method",
                                                   sections.get("proposed method", ""))),
        "experiment_text": sections.get("experiments",
                                         sections.get("experimental results", "")),
        "raw_sections": sections,
    }


def _extract_sections(content: str) -> Dict[str, str]:
    """提取所有 section/subsection 的文本"""
    sections = {}
    # 匹配 \section{...} 到下一个 \section{...} 或 \end{document}
    pattern = r'\\section\{([^}]+)\}(.*?)(?=\\section\{|\\end\{document\})'
    for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE):
        sec_name = match.group(1).strip().lower()
        sec_text = _clean_latex(match.group(2))
        sections[sec_name] = sec_text
    return sections


def _clean_latex(text: str) -> str:
    """清理 LaTeX 标记，保留纯文本"""
    # 移除注释
    text = re.sub(r'%.*', '', text)
    # 移除 \label{...}, \ref{...}, \cite{...}
    text = re.sub(r'\\(?:label|ref|cite|cref|Cref|eqref)\{[^}]*\}', '', text)
    # 替换 \textbf{...} 为纯文本
    text = re.sub(r'\\text(?:bf|it|tt|em|sc)?\{([^}]*)\}', r'\1', text)
    # 替换数学模式
    text = re.sub(r'\$[^$]*\$', 'MATH', text)
    text = re.sub(r'\\\[.*?\\\]', 'MATH', text, flags=re.DOTALL)
    # 移除剩余 LaTeX 命令
    text = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', text)
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    # 清理标点
    text = re.sub(r'[{}$]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ═══════════════════════════════════════════════════════════════
# 解析与转换
# ═══════════════════════════════════════════════════════════════

def _parse_json_response(raw: str) -> Optional[Dict]:
    """从 LLM 响应中提取 JSON"""
    if not raw or not raw.strip():
        return None

    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    # 直接解析
    try:
        result = json.loads(raw)
        if "core_contribution" in result or "innovation_points" in result:
            return result
    except json.JSONDecodeError:
        pass

    # 提取 JSON 块
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _dict_to_brief(d: Dict) -> ContentBrief:
    """将解析后的 dict 转为 ContentBrief"""
    innovations = []
    for ip in d.get("innovation_points", []):
        innovations.append(InnovationPoint(
            name=ip.get("name", ""),
            description=ip.get("description", ""),
            visual_hint=ip.get("visual_hint", ""),
            importance=ip.get("importance", 2),
            related_modules=ip.get("related_modules", []),
        ))

    figure_needs = []
    for fn in d.get("figure_needs", []):
        figure_needs.append(FigureNeed(
            purpose=fn.get("purpose", ""),
            target_audience=fn.get("target_audience", "reviewer"),
            must_show=fn.get("must_show", []),
            key_message=fn.get("key_message", ""),
            suggested_layout=fn.get("suggested_layout", "pipeline"),
            suggested_fig_type=fn.get("suggested_fig_type", "teaser"),
            priority=fn.get("priority", 2),
        ))

    return ContentBrief(
        core_contribution=d.get("core_contribution", ""),
        method_name=d.get("method_name", ""),
        narrative_flow=d.get("narrative_flow", []),
        innovation_points=innovations,
        figure_needs=figure_needs,
        key_modules=d.get("key_modules", []),
    )


# ═══════════════════════════════════════════════════════════════
# 规则提取（LLM 失败时的降级方案）
# ═══════════════════════════════════════════════════════════════

def _rule_based_analysis(paper_content: Dict) -> ContentBrief:
    """当 LLM 不可用时，用规则从文本中提取"""
    title = paper_content.get("title", "Untitled")
    abstract = paper_content.get("abstract", "")
    method_text = paper_content.get("method_text", "")

    # 从 abstract 提取核心贡献
    core = title
    for sentence in re.split(r'[.!?]', abstract):
        for kw in ["propose", "present", "introduce", "contribute"]:
            if kw in sentence.lower():
                core = sentence.strip()
                break

    # 从文本提取创新点关键词
    innovations = []
    for kw in ["novel", "new", "propose", "introduce", "first"]:
        matches = re.findall(
            rf'[^.]*\b{kw}\b[^.]{{10,100}}\.',
            abstract + " " + method_text[:3000],
            re.IGNORECASE,
        )
        for m in matches[:2]:
            clean = re.sub(r'\s+', ' ', m.strip())[:100]
            innovations.append(InnovationPoint(
                name=clean[:30],
                description=clean,
                importance=1 if kw == "novel" else 2,
            ))
    innovations = innovations[:5]

    # 默认图表需求
    figure_needs = [
        FigureNeed(
            purpose="Main architecture overview",
            key_message="The overall framework of the proposed method",
            suggested_layout="pipeline",
            suggested_fig_type="teaser",
            priority=1,
        ),
    ]

    return ContentBrief(
        core_contribution=core,
        method_name=title[:30],
        narrative_flow=["Problem", "Motivation", "Approach", "Validation"],
        innovation_points=innovations,
        figure_needs=figure_needs,
    )


def _validate_brief(brief: ContentBrief, paper_content: Dict) -> ContentBrief:
    """验证和补全 ContentBrief"""
    # 确保有核心贡献
    if not brief.core_contribution:
        brief.core_contribution = paper_content.get("title", "Proposed Method")

    # 确保至少有一个 teaser 图需求
    has_teaser = any(
        fn.suggested_fig_type == "teaser" for fn in brief.figure_needs
    )
    if not has_teaser and brief.figure_needs:
        brief.figure_needs[0].suggested_fig_type = "teaser"
        brief.figure_needs[0].suggested_layout = "pipeline"
        brief.figure_needs[0].priority = 1
    elif not has_teaser:
        brief.figure_needs.append(FigureNeed(
            purpose="Main architecture overview",
            key_message="The overall framework",
            suggested_layout="pipeline",
            suggested_fig_type="teaser",
            priority=1,
        ))

    # 按 priority 排序
    brief.figure_needs.sort(key=lambda fn: fn.priority)

    return brief


# ═══════════════════════════════════════════════════════════════
# 序列化工具
# ═══════════════════════════════════════════════════════════════

def brief_to_dict(brief: ContentBrief) -> Dict:
    """将 ContentBrief 转为可序列化的 dict"""
    result = {
        "core_contribution": brief.core_contribution,
        "method_name": brief.method_name,
        "narrative_flow": brief.narrative_flow,
        "innovation_points": [asdict(ip) for ip in brief.innovation_points],
        "figure_needs": [asdict(fn) for fn in brief.figure_needs],
        "key_modules": brief.key_modules,
    }
    return result


def brief_to_json(brief: ContentBrief) -> str:
    """将 ContentBrief 序列化为 JSON"""
    return json.dumps(brief_to_dict(brief), indent=2, ensure_ascii=False)
