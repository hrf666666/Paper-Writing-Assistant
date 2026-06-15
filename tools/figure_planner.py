# -*- coding: utf-8 -*-
"""
Tool: 图表规划器 v9.2 (Figure Planner)

核心升级（vs v9.1）：
1. 两阶段规划：先 ContentAnalyzer 凝练内容，再 LLM 规划
2. 输出含 layout_template + design_constraints 的增强 plan
3. 图表需求与论文叙事深度联动
4. 实验数据图主动获取

依赖: api/openai_compatible.py, tools/content_analyzer.py
"""

import json
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Plan Prompt 模板（v9.2 增强） ──

_PLAN_SYSTEM_PROMPT = """You are an expert academic figure planner for IEEE TCSVT/TIP journal papers.
Your task is to analyze a paper's methodology and plan the figures needed.

Key principles:
1. ONE figure = ONE story. If a figure tries to say too much, split it.
2. Main figure (Fig.1 Teaser): captures the CORE idea of the entire method in one glance.
3. Supporting figures: show specific innovation details, one per innovation point.
4. Data figures: comparison tables, ablation charts, performance plots.
5. Module-level connections only (not component-level) to reduce visual clutter.
6. Group functionally related elements with dashed boxes / light backgrounds.

IMPORTANT: You must assign a layout_template to EACH architecture/teaser/module_detail figure.
Available layout templates:
- pipeline: Left-to-right sequential flow (best for overall framework)
- dual_branch: Two branches that split and merge (best for dual-path architectures)
- pyramid: Top-to-bottom hierarchy (best for data→feature→output layers)
- encoder_decoder: Symmetric hourglass shape (best for encoder-decoder)
- parallel: Multiple parallel streams merging (best for multi-stream processing)
- recursive: Cyclic/recursive structure with feedback loops

Output MUST be valid JSON. No markdown, no explanation outside JSON."""

_PLAN_USER_PROMPT = """Analyze the following paper content and plan the figures.

## Paper Title
{title}

## Abstract
{abstract}

## Method Description
{method_text}

## Innovation Points
{innovations}

## Content Analysis (from Content Analyzer)
{content_brief}

## Target Venue
{venue}

## Available Experiment Data
{experiment_data}

## Output Format (JSON)
Return a JSON object with this exact structure:
{{
  "figures": [
    {{
      "fig_id": "fig1",
      "fig_type": "teaser",
      "fig_role": "main",
      "title": "Overall Architecture of ...",
      "caption": "The overall framework of ...",
      "size_type": "double",
      "layout_direction": "left_to_right",
      "layout_template": "pipeline",
      "design_constraints": {{
        "highlight_modules": ["m3"],
        "balance_preference": "symmetric",
        "group_style": "dashed_box"
      }},
      "key_message": "One-glance takeaway for reviewers",
      "modules": [
        {{"id": "m1", "label": "Light Field Input", "group": "input", "is_innovation": false}},
        {{"id": "m2", "label": "Signal Decomposition", "group": "core", "is_innovation": true}}
      ],
      "connections": [
        {{"from": "m1", "to": "m2", "label": ""}}
      ],
      "groups": [
        {{"id": "g1", "label": "Physical Prior", "module_ids": ["m2", "m3"], "style": "dashed_box"}}
      ],
      "annotations": ["Key insight: three-layer decomposition"]
    }}
  ]
}}

Rules:
- fig_type: "teaser" | "module_detail" | "ablation" | "comparison" | "qualitative"
- fig_role: "main" | "supporting"
- size_type: "single" (3.5") | "double" (7.16") | "teaser" (7.16" x 3.5")
- layout_template: one of [pipeline, dual_branch, pyramid, encoder_decoder, parallel, recursive]
- layout_template is REQUIRED for teaser and module_detail figures
- key_message: what a reviewer understands from this figure in 5 seconds
- Keep module labels ≤ 3 words each
- Max 8 modules per figure (split if more)
- Always include a teaser figure as fig1
- design_constraints.highlight_modules: list of module IDs that should be visually prominent
- design_constraints.balance_preference: "symmetric" | "left_heavy" | "right_heavy"
"""


def plan_figures(
    paper_content: Dict,
    venue: str = "IEEE TCSVT",
    experiment_data: Optional[Dict] = None,
    model_alias: str = "glm_5_2",
    content_brief: Optional[Dict] = None,
) -> Dict:
    """
    Plan figures from paper content using LLM + Content Analysis.

    v9.2: 如果提供 content_brief，将其纳入规划 prompt。

    Args:
        paper_content: dict with keys: title, abstract, method_text, innovations
        venue: target venue name
        experiment_data: optional experiment results
        model_alias: LLM model alias
        content_brief: optional ContentBrief dict from content_analyzer

    Returns:
        Figure plan dict with "figures" list
    """
    from api.openai_compatible import query_model

    title = paper_content.get("title", "Untitled")
    abstract = paper_content.get("abstract", "")
    method_text = paper_content.get("method_text", "")[:4000]
    innovations = paper_content.get("innovations", [])
    if isinstance(innovations, list):
        innovations = "\n".join(f"- {inn}" for inn in innovations)

    exp_str = "None"
    if experiment_data:
        exp_str = json.dumps(experiment_data, indent=2, ensure_ascii=False)[:2000]

    brief_str = "None"
    if content_brief:
        brief_str = json.dumps(content_brief, indent=2, ensure_ascii=False)[:3000]

    prompt = _PLAN_USER_PROMPT.format(
        title=title,
        abstract=abstract[:2000],
        method_text=method_text,
        innovations=innovations,
        content_brief=brief_str,
        venue=venue,
        experiment_data=exp_str,
    )

    logger.info("[FigurePlanner] 调用 LLM 规划图表...")
    raw = query_model(prompt, model_alias, system_prompt=_PLAN_SYSTEM_PROMPT,
                      temperature=0.3, max_tokens=4096)

    logger.debug(f"[FigurePlanner] 原始响应 (前500字): {raw[:500]}")

    # 解析 JSON
    plan = _parse_json_response(raw)

    if not plan or "figures" not in plan:
        logger.warning(f"[FigurePlanner] {model_alias} 返回无效 JSON，尝试备选模型")
        for fallback_alias in ["qwen3_7_max", "tp_qwen3_7_max", "glm_5"]:
            if fallback_alias == model_alias:
                continue
            try:
                logger.info(f"[FigurePlanner] 尝试备选模型: {fallback_alias}")
                raw = query_model(prompt, fallback_alias, system_prompt=_PLAN_SYSTEM_PROMPT,
                                  temperature=0.3, max_tokens=4096)
                plan = _parse_json_response(raw)
                if plan and "figures" in plan:
                    logger.info(f"[FigurePlanner] 备选模型 {fallback_alias} 成功")
                    break
            except Exception as e:
                logger.warning(f"[FigurePlanner] 备选模型 {fallback_alias} 失败: {e}")
                continue

    if not plan or "figures" not in plan:
        logger.warning("[FigurePlanner] 所有模型均返回无效，使用默认计划")
        plan = _default_plan(paper_content, venue, content_brief)

    # 验证和补全
    plan = _validate_plan(plan, venue, content_brief)

    logger.info(f"[FigurePlanner] 规划完成: {len(plan['figures'])} 张图表")
    return plan


def plan_figures_with_content_analysis(
    tex_path: str,
    venue: str = "IEEE TCSVT",
    text_model_alias: str = "glm_5_2",
) -> Dict:
    """
    v9.2 完整流程：从 LaTeX 提取 → 内容分析 → 图表规划。

    Args:
        tex_path: .tex 文件路径
        venue: 目标 venue
        text_model_alias: LLM 模型

    Returns:
        Figure plan dict
    """
    from tools.content_analyzer import analyze_from_tex, brief_to_dict

    # Phase 1: 内容分析
    logger.info("[FigurePlanner] Phase 1: 内容分析")
    brief = analyze_from_tex(tex_path, text_model_alias)
    brief_dict = brief_to_dict(brief)

    # Phase 2: 规划
    paper_content = _extract_from_tex(tex_path)
    logger.info("[FigurePlanner] Phase 2: 图表规划")
    return plan_figures(
        paper_content, venue,
        model_alias=text_model_alias,
        content_brief=brief_dict,
    )


# 向后兼容
def plan_figures_from_tex(tex_path: str, venue: str = "IEEE TCSVT") -> Dict:
    """从 LaTeX 文件中提取论文内容并规划图表（v9.1 兼容接口）"""
    paper_content = _extract_from_tex(tex_path)
    return plan_figures(paper_content, venue)


# ═══════════════════════════════════════════════════════════════
# 内部工具函数
# ═══════════════════════════════════════════════════════════════

def _parse_json_response(raw: str) -> Optional[Dict]:
    """从 LLM 响应中提取 JSON"""
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def _extract_from_tex(tex_path: str) -> Dict:
    """从 LaTeX 文件提取论文结构"""
    with open(tex_path, "r", encoding="utf-8") as f:
        content = f.read()

    title_match = re.search(r'\\title\{(.+?)\}', content, re.DOTALL)
    title = title_match.group(1).strip() if title_match else "Untitled"

    abs_match = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', content, re.DOTALL)
    abstract = abs_match.group(1).strip() if abs_match else ""

    sections = []
    for sec_name in ["Introduction", "Methodology", "Method", "Proposed Method", "Approach"]:
        pattern = rf'\\section\{{{sec_name}\}}(.*?)(?=\\section\{{|\\end\{{document\}})'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1)
            text = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', text)
            text = re.sub(r'\\[a-zA-Z]+', '', text)
            text = re.sub(r'[{}$]', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            sections.append(text)

    method_text = "\n\n".join(sections)[:4000]

    innovations = []
    for keyword in ["propose", "introduce", "novel", "contribute", "framework", "architecture"]:
        pattern = rf'[^.]*\b{keyword}\b[^.]*\.'
        matches = re.findall(pattern, abstract + " " + method_text[:2000], re.IGNORECASE)
        innovations.extend(matches[:2])
    innovations = innovations[:5]

    return {
        "title": title,
        "abstract": abstract,
        "method_text": method_text,
        "innovations": innovations,
    }


def _default_plan(paper_content: Dict, venue: str,
                  content_brief: Optional[Dict] = None) -> Dict:
    """LLM 失败时的默认图表计划"""
    title = paper_content.get("title", "Method")

    # 如果有内容分析结果，利用其中的信息
    if content_brief:
        method_name = content_brief.get("method_name", title[:50])
        innovations = content_brief.get("innovation_points", [])
        key_modules = content_brief.get("key_modules", [])
    else:
        method_name = title[:50]
        innovations = []
        key_modules = []

    # 构建模块
    modules = []
    connections = []
    if key_modules:
        for i, km in enumerate(key_modules[:8]):
            mid = km.get("id", f"m{i+1}")
            label = km.get("label", f"Module {i+1}")
            is_inn = any(
                ip.get("name", "").lower() in label.lower()
                for ip in innovations
            )
            modules.append({
                "id": mid,
                "label": label[:30],
                "group": km.get("role", "processing"),
                "is_innovation": is_inn,
            })
            if i > 0:
                connections.append({"from": key_modules[i-1].get("id", f"m{i}"),
                                    "to": mid, "label": ""})
    else:
        modules = [
            {"id": "m1", "label": "Input", "group": "input", "is_innovation": False},
            {"id": "m2", "label": "Feature Extraction", "group": "processing", "is_innovation": False},
            {"id": "m3", "label": "Core Module", "group": "processing", "is_innovation": True},
            {"id": "m4", "label": "Output", "group": "output", "is_innovation": False},
        ]
        connections = [
            {"from": "m1", "to": "m2", "label": ""},
            {"from": "m2", "to": "m3", "label": ""},
            {"from": "m3", "to": "m4", "label": ""},
        ]

    return {
        "figures": [{
            "fig_id": "fig1",
            "fig_type": "teaser",
            "fig_role": "main",
            "title": f"Overall Architecture of {method_name}",
            "caption": "The overall framework of the proposed method.",
            "size_type": "teaser",
            "layout_direction": "left_to_right",
            "layout_template": "pipeline",
            "key_message": content_brief.get("core_contribution", "Proposed method framework") if content_brief else "Proposed method framework",
            "modules": modules,
            "connections": connections,
            "groups": [],
            "annotations": [],
        }]
    }


def _validate_plan(plan: Dict, venue: str,
                   content_brief: Optional[Dict] = None) -> Dict:
    """验证和补全图表计划"""
    figures = plan.get("figures", [])

    # 确保至少有一个 teaser
    has_teaser = any(f.get("fig_type") == "teaser" for f in figures)
    if not has_teaser and figures:
        figures[0]["fig_type"] = "teaser"
        figures[0]["fig_role"] = "main"
        if figures[0].get("size_type") not in ("teaser", "double"):
            figures[0]["size_type"] = "teaser"

    # 补全缺失字段
    for fig in figures:
        fig.setdefault("fig_role", "supporting")
        fig.setdefault("size_type", "single")
        fig.setdefault("layout_direction", "left_to_right")
        fig.setdefault("layout_template", "")
        fig.setdefault("key_message", fig.get("title", ""))
        fig.setdefault("design_constraints", {})
        fig.setdefault("modules", [])
        fig.setdefault("connections", [])
        fig.setdefault("groups", [])
        fig.setdefault("annotations", [])
        fig.setdefault("title", fig.get("fig_id", "Figure"))
        fig.setdefault("caption", "")

        # 架构图必须有 layout_template
        if fig.get("fig_type") in ("teaser", "module_detail") and not fig.get("layout_template"):
            fig["layout_template"] = _infer_layout_template(fig)

        # 限制模块数
        if len(fig["modules"]) > 10:
            logger.warning(f"[FigurePlanner] {fig['fig_id']} 模块过多({len(fig['modules'])})，截断为10")
            fig["modules"] = fig["modules"][:10]

    plan["figures"] = figures
    return plan


def _infer_layout_template(fig: Dict) -> str:
    """从图表结构推断布局模板"""
    modules = fig.get("modules", [])
    connections = fig.get("connections", [])

    # 计算出度和入度
    out_degree = {}
    in_degree = {}
    for m in modules:
        out_degree[m["id"]] = 0
        in_degree[m["id"]] = 0
    for c in connections:
        if c["from"] in out_degree:
            out_degree[c["from"]] += 1
        if c["to"] in in_degree:
            in_degree[c["to"]] += 1

    has_branch = any(d >= 2 for d in out_degree.values())
    has_merge = any(d >= 2 for d in in_degree.values())

    if has_branch and has_merge:
        return "dual_branch"
    if has_branch:
        return "parallel"
    return "pipeline"
