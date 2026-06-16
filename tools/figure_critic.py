# -*- coding: utf-8 -*-
"""
Tool: 图表评审器 v10.0

架构原则：
- **MD 引导** = 评审标准（规则书）
- **Vision LLM** = 评审员（运动员）
- **Python** = 编排器（裁判：调用 LLM、解析结果、判断是否通过）
"""

import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_SKILL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "skills", "figure_tikz_gen")


def evaluate_figure(
    png_path: str,
    fig_plan: Dict,
    vision_model_alias: str = "tp_qwen3_6_plus",  # v14: qwen3.6-plus 多模态
    tikz_code: Optional[str] = None,
) -> Dict:
    """
    评审一张图表（v10）。

    Python 职责：加载 MD 引导 → 构造 prompt → 调用 Vision LLM → 解析结果
    Vision LLM 职责：看图 + 读规范 → 输出结构化评价
    """
    if not os.path.exists(png_path):
        return {"overall": 0, "passed": False,
                "error": f"PNG not found: {png_path}"}

    # 1. 加载评审引导
    eval_guide = _load_guide("evaluate_guide.md")

    # 2. 构造 prompt
    fig_id = fig_plan.get("fig_id", "?")
    title = fig_plan.get("title", "")
    caption = fig_plan.get("caption", "")
    fig_type = fig_plan.get("fig_type", "")
    modules = fig_plan.get("modules", [])
    innovations = [m.get("label", "") for m in modules if m.get("is_innovation")]
    groups = fig_plan.get("groups", [])

    modules_desc = "\n".join(
        f"  - {'[INNOVATION] ' if m.get('is_innovation') else ''}{m.get('label', m.get('id', ''))}"
        for m in modules
    )
    groups_desc = "\n".join(
        f"  - {g.get('label', g.get('id', ''))}: {g.get('module_ids', [])}"
        for g in groups
    )

    tikz_context = ""
    if tikz_code:
        tikz_context = f"\n## TikZ Source Code (for reference)\n```latex\n{tikz_code[:2000]}\n```\n"

    prompt = f"""Evaluate this academic paper figure.

## Evaluation Guide
{eval_guide}

## Figure Information
- **Figure ID**: {fig_id}
- **Type**: {fig_type}
- **Title**: {title}
- **Caption**: {caption}

## Expected Modules (what SHOULD be in the figure)
{modules_desc}

## Expected Groups
{groups_desc}

## Innovation Modules (must be visually prominent)
{chr(10).join('- ' + i for i in innovations) if innovations else 'None specified'}
{tikz_context}
## Instructions
1. Look at the figure image carefully
2. Score each dimension (1-10) according to the evaluation guide
3. Identify specific issues with severity levels
4. Provide concrete fix suggestions for each issue
5. Output ONLY valid JSON (no markdown, no explanation)

## Output Format
```json
{{
  "scores": {{
    "content_completeness": <1-10>,
    "information_clarity": <1-10>,
    "visual_design": <1-10>
  }},
  "overall": <weighted average: content*0.4 + clarity*0.35 + design*0.25>,
  "passed": <true if overall >= 7.0 AND all dimensions >= 6>,
  "issues": [
    {{
      "dimension": "content_completeness|information_clarity|visual_design",
      "severity": "high|medium|low",
      "description": "what is wrong",
      "suggestion": "how to fix it in TikZ"
    }}
  ],
  "summary": "one sentence summary"
}}
```"""

    # 3. 调用 Vision LLM
    logger.info(f"[Critic] Vision LLM 评审: {fig_id}")
    try:
        from api.openai_compatible import query_model
        from config.api_config import MODEL_ALIASES

        # Vision 模型需要特殊调用
        cfg = MODEL_ALIASES.get(vision_model_alias, {})
        if not cfg:
            logger.warning(f"[Critic] 未知模型: {vision_model_alias}")
            return _default_pass()

        from api.openai_compatible import create_client_for_model

        try:
            client = create_client_for_model(
                vision_model_alias,
                max_tokens=4096,
                temperature=0.3,
            )
        except Exception as e:
            logger.warning(f"[Critic] 创建客户端失败 {vision_model_alias}: {e}")
            return _default_pass()

        response = client.query_vision(
            text_prompt=prompt,
            image_paths=[png_path],
            max_tokens=4096,
            temperature=0.3,
        )

    except Exception as e:
        logger.error(f"[Critic] Vision LLM 调用失败: {e}")
        return _default_pass()

    # 4. 解析 LLM 输出
    return _parse_evaluation(response)


def _parse_evaluation(response: str) -> Dict:
    """解析 LLM 的评审输出（v10.1: 多层回退策略）"""
    response = response.strip()

    # ── 策略 1: 直接解析 ──
    try:
        result = json.loads(response)
        return _normalize_evaluation(result)
    except json.JSONDecodeError:
        pass

    # ── 策略 2: 去掉 markdown 代码块后再解析 ──
    text = response
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.find("```", start)
        if end == -1:
            end = len(text)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        # 跳过可能的语言标记行（如 ```json, ```latex）
        first_newline = text.find("\n", start)
        if first_newline != -1:
            end = text.find("```", first_newline)
            if end == -1:
                end = len(text)
            text = text[first_newline + 1:end].strip()
        else:
            text = text[start:].strip()

    try:
        result = json.loads(text)
        return _normalize_evaluation(result)
    except json.JSONDecodeError:
        pass

    # ── 策略 3: 找最外层 { ... } 平衡匹配 ──
    brace_result = _extract_balanced_json(text)
    if brace_result:
        try:
            result = json.loads(brace_result)
            return _normalize_evaluation(result)
        except json.JSONDecodeError:
            pass

    # ── 策略 4: 修复常见 LLM 输出问题后解析 ──
    fixed = _fix_common_json_errors(text)
    try:
        result = json.loads(fixed)
        return _normalize_evaluation(result)
    except json.JSONDecodeError:
        pass

    # ── 所有策略都失败 ──
    logger.error("[Critic] JSON 解析失败（所有回退策略耗尽）")
    logger.debug(f"[Critic] 原始响应前500字符: {response[:500]}")
    return {"overall": 0, "passed": False, "issues": [],
            "summary": "Failed to parse evaluation (all fallback strategies exhausted)"}


def _extract_balanced_json(text: str) -> Optional[str]:
    """用括号平衡匹配提取最外层 JSON 对象"""
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        c = text[i]
        if escape_next:
            escape_next = False
            continue
        if c == "\\":
            escape_next = True
            continue
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    # 没找到平衡的闭合
    return None


def _fix_common_json_errors(text: str) -> str:
    """修复 LLM 输出中的常见 JSON 错误"""
    import re
    # 修复尾部逗号（JSON 标准不允许）
    text = re.sub(r',\s*([}\]])', r'\1', text)
    # 修复单引号 → 双引号（简单场景）
    text = re.sub(r"(?<![a-zA-Z])'([^']*)'(?=\s*:)", r'"\1"', text)
    # 修复缺少引号的键
    text = re.sub(r'(?<!["\w])(\w+)\s*:', r'"\1":', text)
    return text


def _normalize_evaluation(result: Dict) -> Dict:
    """规范化评审结果，确保必要字段完整"""
    scores = result.get("scores", {})
    content = scores.get("content_completeness", 0)
    clarity = scores.get("information_clarity", 0)
    design = scores.get("visual_design", 0)
    overall = result.get("overall", content * 0.4 + clarity * 0.35 + design * 0.25)

    # 通过判定（v10.1: 所有维度 >= 6 且 overall >= 7.0）
    passed = (
        overall >= 7.0
        and content >= 6
        and clarity >= 6
        and design >= 6
    )

    return {
        "scores": {"content_completeness": content, "information_clarity": clarity, "visual_design": design},
        "overall": round(overall, 2),
        "passed": passed,
        "issues": result.get("issues", []),
        "summary": result.get("summary", ""),
    }


def _load_guide(filename: str) -> str:
    path = os.path.join(_SKILL_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return f"[Guide not found: {filename}]"


def _default_pass():
    """v10.1: LLM 不可用时标记为未通过（不再默认通过）"""
    return {"overall": 0, "passed": False, "issues": [],
            "scores": {"content_completeness": 0, "information_clarity": 0, "visual_design": 0},
            "summary": "Evaluation skipped (LLM unavailable) — NOT auto-passed"}
